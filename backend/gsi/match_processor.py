"""
CounterTrak Match Processor

Processes game state data for an individual CS2 match.
Maintains state between updates and handles temporal sequence analysis.
"""
from gsi.logging_service import match_processor_logger as logger
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
    batch_update_player_match_stats
)

# import payloadextractor and dataclasses
from gsi.payloadextractor import PayloadExtractor, MatchState, PlayerState

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

        # match metadata
        self.match_state: Optional[MatchState] = None
        self.player_states: Dict[str, PlayerState] = {}
        
        # persistence tracking
        self.match_persisted = False
        self.current_round_persisted = False
        self.rounds_persisted: Set[int] = set()

        # round tracking
        self.current_round = 0
        self.round_start_time: Optional[float] = None

        # activity tracking
        self.last_update_time = time.time()
        self.is_completed = False

        logger.info(f"Match processor initialized for match {self.match_id} owned by {owner_steam_id}")

    async def process_payload(self, payload: Dict, is_owner_playing: bool) -> None:
        """
        Process a GSI payload for this match.
        
        Delegates extraction to PayloadExtractor, accumulates state changes,
        and triggers database operations at appropriate moments.
        
        Args:
            payload: The GSI payload from CS2
            is_owner_playing: Whether the payload represents the client owner's state
        """
        try:
            # update the last activity timestamp
            self.last_update_time = time.time()

            # log player information on first payload
            if not self.match_state and 'player' in payload:
                player_name = payload.get('player', {}).get('name', 'unknown')
                player_steam_id = payload.get('player', {}).get('steamid', 'unknown')
                
                if is_owner_playing:
                    logger.info(f"Match {self.match_id} associated with player {player_name} ({player_steam_id})")
                else:
                    logger.info(f"Match {self.match_id} processing spectated player {player_name} ({player_steam_id})")

            # delegate all extraction and change detection to payloadextractor
            processed_data = self.extractor.process_payload(payload)
            
            # extract components from processed data
            match_state = processed_data['match_state']
            player_state = processed_data['player_state']
            changes = processed_data['changes']
            
            # check if we need to create the match record
            if match_state and not self.match_persisted:
                await self._ensure_match_exists(match_state)
            
            # handle round transitions if detected
            if match_state and self.match_state and match_state.round != self.match_state.round:
                logger.info(f"Match {self.match_id}: Round change from {self.match_state.round} to {match_state.round}")
                await self._process_round_transition(
                    old_round=self.match_state.round,
                    new_round=match_state.round,
                    phase=match_state.phase
                )
            
            # update match state and persist match changes
            if match_state:
                # if match exists and has changed, update it
                if self.match_persisted and self.match_state and changes['match']:
                    await update_match(self.match_id, match_state)
                
                # update internal state
                self.match_state = match_state
                self.current_round = match_state.round
                
                # check if the match is completed
                if match_state.phase == "gameover" and not self.is_completed:
                    logger.info(f"Match {self.match_id}: Game over detected")
                    await self._handle_match_completion()
            
            # update player state if owner is playing
            if is_owner_playing and player_state:
                # first ensure the steam account exists
                await ensure_steam_account(player_state.steam_id, player_state.name)
                
                # store the player state in memory only - no database updates here
                self.player_states[player_state.steam_id] = player_state
                
                # process significant events for analytics
                if 'significant_events' in changes:
                    self._process_significant_events(changes['significant_events'])
                
                # removed: no more continuous match stats updates
                # this will now happen only at round transitions
                
        except Exception as e:
            logger.error(f"Error processing payload in match {self.match_id}: {str(e)}")
            logger.exception(e)

    async def _ensure_match_exists(self, match_state: MatchState) -> bool:
        """
        Ensure the match record exists in the database.
        
        Creates it if it doesn't exist yet.
        
        Args:
            match_state: Current match state
            
        Returns:
            True if match exists or was created, False otherwise
        """
        exists = await match_exists(self.match_id)
        
        if exists:
            self.match_persisted = True
            logger.info(f"Found existing match record for {self.match_id}")
            return True
        
        # create new match record
        created_id = await create_match(match_state, self.match_id)
        if created_id:
            self.match_persisted = True
            logger.info(f"Created new match record for {self.match_id}")
            return True
        
        logger.error(f"Failed to create match record for {self.match_id}")
        return False

    async def _process_round_transition(self, old_round: int, new_round: int, phase: str) -> None:
        """
        Process a transition between rounds.

        Args:
            old_round: The previous round number
            new_round: The new round number
            phase: The current match phase
        """
        logger.info(f"Match {self.match_id}: Processing round transition from {old_round} to {new_round}")

        # case 1: old round data persistence - must happen first
        if old_round > 0 and old_round not in self.rounds_persisted:
            # get the winner info for the just-completed round (old_round)
            winning_team = self.extractor.get_round_winner(old_round)
            win_condition = self.extractor.get_round_win_condition(old_round)

            # first update the round with winner information if available
            if winning_team:
                round_exists = await self._ensure_round_exists(old_round, "over")
                if round_exists:
                    await update_round_winner(
                        self.match_id, old_round, winning_team, win_condition
                    )
                    logger.info(f"Match {self.match_id}: Updated round {old_round} winner: {winning_team}")

            # then persist all data for the completed round
            await self._persist_round_data(old_round)
            logger.info(f"Match {self.match_id}: Finalized data for round {old_round}")

        # case 2: new round initialization - must happen second
        if phase == 'live' and new_round > 0:
            # check if the new round already exists
            round_exists = await self._ensure_round_exists(new_round, phase)
            if round_exists:
                logger.info(f"Match {self.match_id}: Round {new_round} record already exists")
            else:
                # create new round record
                await create_round(
                    self.match_id, new_round, phase, None, None
                )
                logger.info(f"Match {self.match_id}: Created initial record for round {new_round}")

            # set up for the new round
            self.round_start_time = time.time()
            self.current_round_persisted = False
    
    # additional helper method
    async def _ensure_round_exists(self, round_number, phase):
        """Check if round exists, return True if it does, False if it doesn't"""
        exists = await round_exists(self.match_id, round_number)
        return exists

    def _process_significant_events(self, events: List[Dict]) -> None:
        """
        Process significant game events for analytics.
        
        Logs important events for future analysis.
        
        Args:
            events: List of significant event dictionaries
        """
        for event in events:
            event_type = event.get('type')
            
            if event_type == 'player_kill':
                player_id = event.get('player_id')
                weapon = event.get('weapon')
                kill_count = event.get('kill_count', 1)
                timestamp = event.get('timestamp')
                
                logger.info(f"Player {player_id} got {kill_count} kill(s) with {weapon} at {timestamp}")
                
            elif event_type == 'weapon_activated':
                player_id = event.get('player_id')
                weapon = event.get('weapon')
                timestamp = event.get('timestamp')
                
                logger.debug(f"Player {player_id} activated {weapon} at {timestamp}")
                
            elif event_type == 'round_over':
                round_number = event.get('round_number')
                winner = event.get('winner')
                condition = event.get('condition')
                
                logger.info(f"Round {round_number} over. Winner: {winner}, Condition: {condition}")

    async def _persist_round_data(self, round_number: int) -> None:
        """
        Persist all data for a completed round.
        
        This includes:
        1. Round record
        2. Player round states
        3. Player weapons
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
                    logger.info(f"Updated round winner for match {self.match_id}, round {round_number}")
            else:
                # create new round
                await create_round(
                    self.match_id, round_number, 
                    self.match_state.phase, winning_team, win_condition
                )
                logger.info(f"Created round record for match {self.match_id}, round {round_number}")
            
            # first, create player states and get their ids
            player_state_ids = await batch_create_player_states(
                self.match_id, round_number, self.player_states
            )
            logger.info(f"Created {len(player_state_ids)} player states for match {self.match_id}, round {round_number}")
            
            # then, explicitly create weapon states using the ids
            if player_state_ids:
                weapon_count = await batch_create_player_weapons(
                    self.match_id, round_number, self.player_states, player_state_ids
                )
                logger.info(f"Created {weapon_count} weapon states for match {self.match_id}, round {round_number}")
            
            # finally, update match stats
            if self.player_states:
                await batch_update_player_match_stats(self.match_id, self.player_states)
                
            # mark round as persisted
            self.rounds_persisted.add(round_number)
            
        except Exception as e:
            logger.error(f"Error persisting round data for match {self.match_id}, round {round_number}: {str(e)}")
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
                self.match_id, ct_score, t_score, total_rounds
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

    # accessor methods for match statistics
    
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
