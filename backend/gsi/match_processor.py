"""
CounterTrak Match Processor

Processes game state data for an individual CS2 match.
Maintains state between updates and handles temporal sequence analysis.
"""
from gsi.logging_service import match_processor_logger as logger, highlight_logger
from gsi.logging_service import get_colored_logger
import asyncio
import time
from typing import Dict, Optional, List, Set
from django.utils import timezone

# import from django_integration - now with properly separated operations
from gsi.django_integration import (
    # match operations
    match_exists, create_match, update_match, complete_match,
    # round operations
    round_exists, create_round, update_round_winner,
    # player state operations
    batch_create_player_states, batch_create_player_weapons, ensure_steam_account,
    # match stats operations
    update_player_match_stats
)

# import payloadextractor and dataclasses
from gsi.payloadextractor import (
    PayloadExtractor, 
    MatchState,
    RoundState,
    PlayerState, 
    WeaponState
)

round_logger = get_colored_logger('match_processor_rounds', 'light_green')

class MatchProcessor:
    """
    Processes and maintains state for a single CS2 match.
    
    Responsibilities:
    1. Track match state throughout its lifecycle
    2. Accumulate player state changes for batch persistence
    3. Trigger database writes at appropriate times (round end, match completion)
    4. Provide match statistics for the match manager
    """

    def __init__(self, base_match_id: str, full_match_id: str, owner_steam_id: str):
        """
        Initialize a new match processor for a specific match.
        
        Args:
            base_match_id: The match identifier, without an appended UUID
            full_match_id: The complete match ID with an appended UUID
            owner_steam_id: The steam ID of the client owner
        """
        self.base_match_id = base_match_id
        self.match_id = full_match_id
        self.owner_steam_id = owner_steam_id
        self.extractor = PayloadExtractor()

        # metadata fields
        self.match_state: Optional[MatchState] = None
        self.round_state: Optional[RoundState] = None
        self.player_states_history = []
        self.player_states: Dict[str, PlayerState] = {}
        self.weapon_states_history = []
        self.weapon_states: Dict[str, WeaponState] = {}
        
        # persistence tracking
        self.match_persisted = False
        self.rounds_persisted: Set[int] = set()

        # round tracking
        self.current_round = 0
        self.previous_round_phase = None
        self.round_start_time: Optional[float] = None

        # activity tracking
        self.last_update_time = time.time()
        self.is_completed = False

        logger.info(f"Match processor initialized for match {self.match_id} owned by {owner_steam_id}")

    async def handle_payload(self, payload: Dict, is_owner_playing: bool) -> None:
        """Handle a payload for this match"""
        try:
            # update timestamp
            self.last_update_time = time.time()
            
            # log initial payload info (only once)
            if not self.match_state and 'player' in payload:
                self._log_initial_payload_info(payload, is_owner_playing)

            # extract all data
            processed_data = self.extractor.process_payload(payload)
            
            # process entities in order of dependency
            await self._handle_match_data(processed_data)
            await self._handle_round_data(processed_data)
            
            # process player-specific data only if owner is playing
            if is_owner_playing:
                await self._handle_player_data(processed_data)
                await self._handle_weapon_data(processed_data)
                self._process_game_events(processed_data['changes'])
            
        except Exception as e:
            logger.error(f"Error handling payload in match {self.match_id}: {str(e)}")
            logger.exception(e)

    def set_match_state(self, new_state: MatchState) -> None:
        """Update match state and handle associated state changes"""
        if not new_state:
            return
            
        old_state = self.match_state
        self.match_state = new_state
        
        # handle match phase changes
        if old_state and old_state.phase != new_state.phase and new_state.phase == "gameover":
            round_logger.info(f"Match {self.match_id}: Game over detected")
            asyncio.create_task(self._handle_match_completion())

    def set_round_state(self, new_state: RoundState) -> None:
        """Update round state and handle associated state changes"""
        if not new_state:
            return
            
        old_state = self.round_state
        self.round_state = new_state

        if self.current_round != new_state.round_number:
            round_logger.debug(f"Updating self.round_number in {__name__} from {self.current_round} -> {new_state.round_number}")

        self.current_round = new_state.round_number
        
        # handle round phase changes
        if old_state and old_state.phase != new_state.phase and new_state.phase == "over":
            round_logger.info(f"Match {self.match_id}: Round {new_state.round_number} phase changed to 'over'")
            # store in extractor's round history for later reference
            self.extractor.round_history[new_state.round_number] = new_state

    def _log_initial_payload_info(self, payload: Dict, is_owner_playing: bool) -> None:
        """Log initial information about this match"""
        player_name = payload.get('player', {}).get('name', 'unknown')
        player_steam_id = payload.get('player', {}).get('steamid', 'unknown')
        if is_owner_playing:
            logger.info(f"Match {self.match_id} associated with player {player_name} ({player_steam_id})")
        else:
            logger.info(f"Match {self.match_id} processing spectated player {player_name} ({player_steam_id})")

    async def _handle_match_data(self, processed_data: Dict) -> None:
        """Handle match state updates"""
        match_state = processed_data.get('match_state')
        if not match_state:
            return

        # ensure match exists in database
        if not self.match_persisted:
            self.match_persisted = await self.ensure_match(match_state)

        # handle match updates if already persisted
        elif self.match_persisted and self.match_state and self._has_match_changes(match_state):
            await update_match(self.match_id, match_state)

        # update internal state (this will trigger phase change handlers)
        self.set_match_state(match_state)

    async def _handle_round_data(self, processed_data: Dict) -> None:
        """Handle round state updates"""
        round_state = processed_data.get('round_state')
        if not round_state:
            return

        # check for round transitions (when round number changes)
        if self.match_state and self.current_round != round_state.round_number:
            await self._handle_round_transition(
                old_round=self.current_round,
                new_round=round_state.round_number,
                new_round_state=round_state
            )

        # track phase transitions
        if self.round_state and self.round_state.phase != round_state.phase:
            round_logger.info(
                f"Match {self.match_id}: Round {round_state.round_number} " +
                f"phase changed from '{self.previous_round_phase or 'unknown'}' " + 
                f"to '{round_state.phase}'"
            )
            self.previous_round_phase = self.round_state.phase

        # update internal state (this will trigger phase change handlers)
        self.set_round_state(round_state)

    async def _handle_player_data(self, processed_data: Dict) -> None:
        """Handle player state updates"""
        player_state = processed_data.get('player_state')
        if not player_state:
            return

        # ensure steam account exists
        await ensure_steam_account(player_state.steam_id, player_state.name)

        # add to local state
        self._add_player_state(player_state)

        # update match stats if available
        if self.match_persisted:
            await update_player_match_stats(self.match_id, player_state)

    async def _handle_weapon_data(self, processed_data: Dict) -> None:
        """Handle weapon state updates"""
        weapon_states = processed_data.get('weapon_states')
        if not weapon_states:
            return

        # add to local state
        self._add_weapon_states(weapon_states)

    def _process_game_events(self, changes: Dict) -> None:
        """Process significant game events for analytics"""
        if 'significant_events' not in changes:
            return

        for event in changes['significant_events']:
            event_type = event.get('type')

            if event_type == 'player_kill':
                player_id = event.get('player_id')
                weapon = event.get('weapon')
                kill_count = event.get('kill_count', 1)
                logger.info(f"Player {player_id} got {kill_count} kill(s) with {weapon}")

            elif event_type == 'round_over':
                round_number = event.get('round_number')
                winner = event.get('winner')
                condition = event.get('condition')
                logger.info(f"Round {round_number} over. Winner: {winner}, Condition: {condition}")

    async def ensure_match(self, match_state: MatchState) -> bool:
        """Ensure match exists, creating it if necessary"""
        exists = await match_exists(self.match_id)

        if exists:
            self.match_persisted = True
            logger.info(f"Found existing match record for {self.match_id}")
            return True

        # create new match record
        created_id = await create_match(match_state, self.match_id)
        if created_id:
            self.match_persisted = True
            return True

        logger.error(f"Failed to create match record for {self.match_id}")
        return False

    async def ensure_round(self, round_number: int, phase: str,
                          winning_team: Optional[str] = None,
                          win_condition: Optional[str] = None,
                          timestamp: Optional[int] = None) -> bool:
        """Ensure round exists, creating it if necessary"""
        exists = await round_exists(self.match_id, round_number)

        if exists:
            return True

        # create new round record
        if timestamp is None and self.round_state:
            timestamp = self.round_state.timestamp
        elif timestamp is None and self.match_state:
            timestamp = self.match_state.timestamp
        else:
            timestamp = int(time.time())
            highlight_logger.warning(f"A timestamp was instantiated in {__name__}")

        await create_round(
            self.match_id, round_number, phase,
            winning_team, win_condition, timestamp
        )

        round_logger.info(f"Created record for round {round_number} with phase '{phase}'")
        return True

    def _debug_log_payload(self, payload: Dict, indent_level: int = 0) -> None:
        """
        Log a payload structure for debugging purposes.

        Args:
            payload: Dictionary or JSON-like structure to log
            indent_level: Current indentation level
        """
        if not isinstance(payload, dict):
            logger.debug(f"Payload is not a dictionary: {payload}")
            return

        for key, value in payload.items():
            indent_str = ' ' * indent_level
            if not isinstance(value, dict):
                # for non-dictionary values, log key-value pair
                logger.debug(f"{indent_str}{key}: {value}")
            else:
                # for nested dictionaries, log key and recurse
                logger.debug(f"{indent_str}{key}:")
                self._debug_log_payload(value, indent_level + 2)

    async def _handle_round_transition(self, old_round: int, new_round: int, new_round_state: RoundState) -> None:
        """Handle transition between rounds"""
        round_logger.info(f"Match {self.match_id}: Processing round transition from {old_round} to {new_round}")

        # 1. complete the old round if it exists and hasn't been persisted
        if old_round > 0 and old_round not in self.rounds_persisted:
            await self._complete_round(old_round)

        # 2. initialize the new round if it's active
        if (new_round_state.phase in ['freezetime', 'live']) and new_round > 0:
            # check if this round has already been created
            round_existence = await round_exists(self.match_id, new_round)
            if not round_existence:
                # create the new round record
                await self.ensure_round(
                    new_round, new_round_state.phase, None, None, new_round_state.timestamp
                )
            # set up for the new round
            self.round_start_time = time.time()
            logger.info(f"Match {self.match_id}: Initialized round {new_round}")

    async def _complete_round(self, round_number: int) -> None:
        """Complete a round and persist all related data"""
        # get round winner information from the extractor
        winning_team = self.extractor.get_round_winner(round_number)
        win_condition = self.extractor.get_round_win_condition(round_number)

        # first check if round exists
        round_existence = await round_exists(self.match_id, round_number)

        # update round with winner information if available
        if winning_team:
            if round_existence:
                # update existing round with winner info
                await update_round_winner(
                    self.match_id, round_number, winning_team, win_condition
                )
                logger.info(f"Match {self.match_id}: Updated round {round_number} winner: {winning_team}")
            else:
                # create new round directly with winner info
                await create_round(
                    self.match_id, round_number, "over", winning_team, win_condition,
                    self.match_state.timestamp if self.match_state else int(time.time())
                )
                logger.info(f"Match {self.match_id}: Created final round {round_number} record with winner: {winning_team}")
                if not self.match_state:
                    logger.warning(f"A timestamp was instantiated in {__name__}")

        # persist all player and weapon data for this round
        await self._persist_round_data(round_number)

        logger.info(f"Match {self.match_id}: Completed round {round_number}")

    async def _persist_round_data(self, round_number: int) -> None:
        """
        Persist all data for a completed round.

        This includes:
        1. Round record
        2. Player round states
        3. Player weapons (now handled separately)
        4. Updated match stats

        Args:
            round_number: The round number to persist
        """
        if not self.match_state or not self.match_persisted:
            logger.warning(f"Cannot persist round data: match not yet persisted for round {round_number}")
            return

        try:
            # check if round already exists
            round_already_exists = await round_exists(self.match_id, round_number)

            # get round winner information
            winning_team = self.extractor.get_round_winner(round_number)
            win_condition = self.extractor.get_round_win_condition(round_number)

            # create or update round
            if round_already_exists:
                # only update winner info if round exists
                if winning_team:
                    await update_round_winner(
                        self.match_id, round_number, winning_team, win_condition
                    )
            else:
                # create new round
                await create_round(
                    self.match_id, round_number,
                    self.match_state.phase, winning_team, win_condition
                )
                logger.info(f"Created round record for match {self.match_id}, round {round_number}")

            # extract states for this round only
            player_states_to_save = {state.steam_id: state for state in self.player_states_history
                               if state.steam_id in self.player_states}

            # now, with dictionary comprehension completed, persist playerstates
            await batch_create_player_states(
                self.match_id, round_number, player_states_to_save
            )

            # log history of weapon state data
            logger.info(f"Persisting {len(self.weapon_states_history)} weapon states for round {round_number}")

            # group weapon states by player for batch processing
            weapons_by_player = {}
            for weapon in self.weapon_states_history:
                steam_id = weapon.steam_id
                if steam_id not in weapons_by_player:
                    weapons_by_player[steam_id] = {}
                # add weapon with slot as key
                for slot, ws in self.weapon_states.items():
                    if ws.name == weapon.name:
                        weapons_by_player[steam_id][slot] = weapon
                        break
            
            # save weapon states for each player
            for steam_id, weapons in weapons_by_player.items():
                if weapons:
                    weapon_count = await batch_create_player_weapons(
                        self.match_id, round_number, steam_id, weapons
                    )
                    logger.info(f"Created {weapon_count} weapon states for player {steam_id}")
            
            # update match stats
            if player_states_to_save:
                await update_player_match_stats(self.match_id, player_states_to_save)
            
            # clear history for next round
            self.player_states_history = []
            self.weapon_states_history = []
            
            # mark round as persisted
            self.rounds_persisted.add(round_number)

        except Exception as e:
            logger.error(f"Error persisting round data: {str(e)}")
            logger.exception(e)

    async def _handle_match_completion(self) -> None:
        """
        Handle the completion of a match.
        
        Finalizes all data and marks the match as completed.
        """
        if self.is_completed:
            return
            
        self.is_completed = True
        logger.info(f"Match {self.match_id} completed")

        try:
            # calculate final scores
            ct_score = self.match_state.team_ct_score
            t_score = self.match_state.team_t_score
            total_rounds = ct_score + t_score

            logger.info(
                f"Final score - CT: {ct_score}, T: {t_score}, "
                f"Total rounds: {total_rounds}"
            )

            # ensure all rounds are persisted
            for round_num in range(1, self.current_round + 1):
                if round_num not in self.rounds_persisted:
                    logger.info(f"Processing missed round {round_num} during match completion")
                    await self._persist_round_data(round_num)

            # mark match as completed
            success = await complete_match(
                self.match_id, ct_score, t_score, total_rounds, self.match_state.timestamp
            )
            
            if success:
                logger.info(f"Successfully completed match {self.match_id}")
            else:
                logger.warning(f"Failed to mark match {self.match_id} as completed")

        except Exception as e:
            logger.error(f"Error handling match completion for {self.match_id}: {str(e)}")
            logger.exception(e)

    def is_match_completed(self) -> bool:
        """
        Check if the match is completed or has been inactive for too long.
        
        Returns:
            True if the match is completed, False otherwise
        """
        # check explicit completion
        if self.is_completed:
            return True
        
        # check for inactivity
        inactive_seconds = time.time() - self.last_update_time
        if inactive_seconds > 600:  # 10 minutes
            logger.info(f"Match {self.match_id} considered completed due to inactivity")
            return True
        
        return False

    def _add_player_state(self, player_state: PlayerState) -> None:
        """Add a player state to history and update current state"""
        # add to chronological history
        self.player_states_history.append(player_state)
        
        # update current state lookup
        self.player_states[player_state.steam_id] = player_state
        
        # log for debugging
        logger.debug(f"Added player state for {player_state.steam_id}, total states: {len(self.player_states_history)}")

    def _add_weapon_states(self, weapon_states: Dict[str, WeaponState]) -> None:
        """Add weapon states to history and update current states"""
        # add each weapon to history
        for slot, weapon_state in weapon_states.items():
            self.weapon_states_history.append(weapon_state)
            self.weapon_states[slot] = weapon_state
        
        # log for debugging
        logger.debug(f"Added {len(weapon_states)} weapon states, total: {len(self.weapon_states_history)}")

    def _has_match_changes(self, new_state: MatchState) -> bool:
        """Check if there are changes between current and new match state"""
        if not self.match_state:
            return True
            
        # check relevant fields
        for field in ['phase', 'round', 'team_ct_score', 'team_t_score']:
            if getattr(self.match_state, field) != getattr(new_state, field):
                return True
                
        return False

    def _has_round_changes(self, new_state: RoundState) -> bool:
        """Check if there are changes between current and new round state"""
        if not self.round_state:
            return True
            
        # check relevant fields
        for field in ['phase', 'win_team', 'bomb_state', 'win_condition']:
            old_value = getattr(self.round_state, field, None)
            new_value = getattr(new_state, field, None)
            if old_value != new_value:
                return True
                
        return False

#==============================================================================
# accessor methods for match statistics
#==============================================================================

    def get_map_name(self) -> str:
        """Get the map name for this match."""
        return self.match_state.map_name if self.match_state else "unknown"
    
    def get_game_mode(self) -> str:
        """Get the game mode for this match."""
        return self.match_state.mode if self.match_state else "unknown"
    
    def get_match_phase(self) -> str:
        """Get the current match phase."""
        return self.match_state.phase if self.match_state else "unknown"
    
    def get_current_round(self) -> int:
        """Get the current round number."""
        return self.current_round
    
    def get_ct_score(self) -> int:
        """Get the CT team's score."""
        return self.match_state.team_ct_score if self.match_state else 0
    
    def get_t_score(self) -> int:
        """Get the T team's score."""
        return self.match_state.team_t_score if self.match_state else 0
    
    def get_player_count(self) -> int:
        """Get the number of players in this match."""
        return len(self.player_states)
