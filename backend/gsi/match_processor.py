"""
CounterTrak Match Processor

Processes game state data for an individual CS2 match.
Maintains state between updates and handles temporal sequence analysis.
"""
from gsi.logging_service import match_processor_logger as logger, log_to_file
import asyncio
import uuid
import time
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Set
from gsi.django_integration import create_or_update_match, create_or_update_player_state
from asgiref.sync import sync_to_async
from datetime import datetime


# import payloadextractor to leverage original proof-of-concept
from gsi.payloadextractor import PayloadExtractor, MatchState, PlayerState

class MatchProcessor:
    """
    Processes and maintains state for a single CS2 match.
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
        
        # round tracking
        self.current_round = 0
        self.round_start_time: Optional[float] = None
        self.rounds_processed: Set[int] = set()
        
        # activity tracking
        self.last_update_time = time.time()
        self.is_completed = False
        self.match_persisted = False
        
        logger.info(f"Match processor initialized for match {self.match_id} owned by {owner_steam_id}")
    
    async def process_payload(self, payload: Dict, is_owner_playing: bool) -> None:
        """
        Process a GSI payload for this match.
        
        This method:
        1. Updates the match state
        2. Updates player states
        3. Tracks round transitions
        4. Detects match completion
        
        Args:
            payload: The GSI payload from CS2
            is_owner_playing: Whether the payload represents the client owner's state
        """
        try:
            # update the last activity timestamp
            self.last_update_time = time.time()

            if 'player' in payload:
                player_name = payload.get('player', {}).get('name', 'unknown')
                player_steam_id = payload.get('player', {}).get('steamid', 'unknown')

                # for first payload, log association
                if not self.match_state:
                    if is_owner_playing:
                        logger.info(f"Match {self.match_id} associated with player {player_name} ({player_steam_id})")
                    else:
                        logger.info(f"Match {self.match_id} processing spectated player {player_name} ({player_steam_id})")
            
            # always extract match state regardless of who is being observed
            new_match = self.extractor.extract_match_state(payload)
            if new_match:
                # if this is a new round, process the round transition
                if self.match_state and new_match.round != self.match_state.round:
                    logger.info(f"Match {self.match_id}: Round change from {self.match_state.round} to {new_match.round}")
                    await self._process_round_transition(
                        old_round=self.match_state.round,
                        new_round=new_match.round,
                        phase=new_match.phase
                    )
                
                # update the match state
                self.match_state = new_match
                self.current_round = new_match.round
                
                # check if the match is completed
                if new_match.phase == "gameover":
                    logger.info(f"Match {self.match_id}: Game over detected")
                    await self._handle_match_completion()

            # only update player state if this is the owner playing
            if is_owner_playing:
                new_player = self.extractor.extract_player_state(payload)
                if new_player:
                    await self._update_player_state(new_player)
                    # process state changes for analysis
                    await self._process_state_changes(payload)
            
        except Exception as e:
            logger.error(f"Error processing payload in match {self.match_id}: {str(e)}")
    
    async def _process_round_transition(self, old_round: int, new_round: int, phase: str) -> None:
        """
        Process a transition between rounds.
        
        Args:
            old_round: The previous round number
            new_round: The new round number
            phase: The current match phase
        """
        # check if the old round is ready to be persisted
        if self.extractor.should_persist_round(old_round):
            logger.info(f"Match {self.match_id}: Round {old_round} ready for persistence")
            await self._save_round_data(old_round)
            self.rounds_processed.add(old_round)

        # mark as processed if we've already passed it
        if old_round not in self.rounds_processed:
            self.rounds_processed.add(old_round)
            logger.info(f"Match {self.match_id}: Completed round {old_round}")
            await self._save_round_data(old_round)

        if phase == 'over' and new_round > old_round:
            self.round_start_time = time.time()
            logger.info(f"Match {self.match_id}: Starting round {new_round}")
    
    async def _update_player_state(self, player_state: PlayerState) -> None:
        """
        Update a player's state and track changes.
        
        Args:
            player_state: The new player state
        """
        steam_id = player_state.steam_id
        
        # check if we've seen this player before
        if steam_id in self.player_states:
            old_state = self.player_states[steam_id]
            
            # track changes in player state (similar to monitor_state_changes)
            basic_changes = {
                k: v for k, v in vars(player_state).items()
                if k != 'weapons' and getattr(old_state, k) != v
            }
            
            if basic_changes:
                # todo: here we would track significant state changes
                # for performance metrics analysis
                pass
            
            # track weapon changes
            for weapon_slot, new_weapon in player_state.weapons.items():
                if weapon_slot in old_state.weapons:
                    old_weapon = old_state.weapons[weapon_slot]
                    weapon_changes = {
                        k: getattr(new_weapon, k)
                        for k in vars(new_weapon).keys()
                        if getattr(old_weapon, k) != getattr(new_weapon, k)
                    }
                    
                    if weapon_changes:
                        # especially important to track state changes
                        # (active/holstered) for weapon analytics
                        if 'state' in weapon_changes and weapon_changes['state'] == 'active':
                            logger.debug(f"Player {steam_id} activated {new_weapon.name}")
                        elif 'state' in weapon_changes and weapon_changes['state'] == 'holstered':
                            logger.debug(f"Player {steam_id} holstered {new_weapon.name}")
        
        # update the player's state
        self.player_states[steam_id] = player_state
    
    async def _process_state_changes(self, payload: Dict) -> None:
        """
        Process significant state changes for analytics.
        
        This method identifies important events like:
        - Weapon switches
        - Kills/deaths
        - Round victories
        - Economic decisions
        
        Args:
            payload: The GSI payload
        """
        # use existing monitor_state_changes method as a starting point
        # this will log changes but we'll need to enhance it for analytics
        self.extractor.monitor_state_changes(payload)
        
        # todo: additional state change processing for analytics
        # this will be filled in with our specific analytics logic
    
    async def _save_round_data(self, round_number: int) -> None:
        """
        Save the data for a completed round.
        
        Args:
            round_number: The round number to save
        """
        if not self.match_state:
            logger.warning(f"Cannot save round data: match state not available for round {round_number}")
            return

        try:
            # first, check that the Match exists in the database.
            #  if it doesn't, instantiate the record. if it does, update it
            if not self.match_persisted:
                match, created = await create_or_update_match(self.match_state)
                if created:
                    logger.info(f"Created new match record for {self.match_id}")
                else:
                    logger.info(f"Updated existing match record for {self.match_id}")
                self.match_persisted = True

            # get round information directly from the most recent payload,
            #   handling delegated to PayloadExtractor methods
            winning_team = self.extractor.get_round_winner(round_number)
            win_condition = self.extractor.get_round_win_condition(round_number)

            if not winning_team and self.current_round > round_number:
                # if we've moved past this round but don't have winner info,
                #  we can infer it from score changes (fallback logic)
                if self.match_state.team_ct_score > 0:
                    winning_team = "CT"
                    win_condition = "elimination" # default assumption
                elif self.match_state.team_t_score > 0:
                    winning_team = "T"
                    win_condition = "elimination" # default assumption

            # create or update round record
            round_obj, round_created = await create_or_update_round(
                self.match_id, # use full match ID with UUID
                round_number,
                self.match_state.phase,
                winning_team,
                win_condition
            )

            if round_created:
                logger.info(f"Created new round record for match {self.match_id}, round {round_number}")
            else:
                logger.info(f"Updated round record for match {self.match_id}, round {round_number}")

            # save player states for this round
            saved_states = 0
            for steam_id, player in self.player_states.items():
                player_state = await create_or_update_player_state(
                    self.match_id,
                    round_number,
                    player
                )
                if player_state:
                    saved_states += 1

            logger.info(f"Saved {saved_states} player states for match {self.match_id}, round {round_number}")

        except Exception as e:
            logger.error(f"Error saving round data for match {self.match_id}, round {round_number}: {str(e)}")
    
    async def _handle_match_completion(self) -> None:
        """
        Handle the completion of a match.
        """
        if not self.is_completed and self.match_state:
            self.is_completed = True
            logger.info(f"Match {self.match_id} completed")

            try:
                # save final match stats
                ct_score = self.match_state.team_ct_score
                t_score = self.match_state.team_t_score
                total_rounds = ct_score + t_score

                logger.info(
                    f"Final score - CT: {ct_score}, T: {t_score}, "
                    f"Total rounds: {total_rounds}"
                )

                # ensure all rounds are saved first
                for round_num in range(1, self.current_round + 1):
                    if round_num not in self.rounds_processed:
                        logger.info(f"Processing missed round {round_num} during match completion")
                        await self._save_round_data(round_num)

                # update match record with end timestamp and final scores
                from django.db import connection
                end_timestamp = datetime.now()

                # using Django's database connection for a raw SQL update
                #  this demonstrates SQL usage for data insertion
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        UPDATE matches_match
                        SET end_timestamp = %s,
                            rounds_played = %s,
                            team_ct_score = %s,
                            team_t_score = %s
                        WHERE match_id = %s
                        """,
                        [end_timestamp, total_rounds, ct_score, t_score, self.match_id]
                    )
                    logger.info(f"Updated match record with final stats for {self.match_id}")

                # update final player match stats for each player
                for steam_id, player in self.player_states.items():
                    # this SQL demonstrates an UPSERT operation
                    with connection.cursor() as cursor:
                        cursor.execute(
                            """
                            INSERT INTO stats_playermatchstat
                                (steam_account_id, match_id, kills, deaths, assists, mvps, score)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT (steam_account_id, match_id)
                            DO UPDATE SET
                                kills = EXCLUDED.kills,
                                deaths = EXCLUDED.deaths,
                                assists = EXCLUDED.assists,
                                mvps = EXCLUDED.mvps,
                                score = EXCLUDED.score
                            """,
                            [
                                steam_id,
                                self.match_id,
                                player.match_kills,
                                player.match_deaths,
                                player.match_assists,
                                player.match_mvps,
                                player.match_score
                            ]
                        )
                    logger.info(f"Updated final stats for player {steam_id} in match {self.match_id}")

            except Exception as e:
                logger.error(f"Error handling match completion for {self.match_id}: {str(e)}")
    
    def is_match_completed(self) -> bool:
        """
        Check if the match is completed or has been inactive for too long.
        
        A match is considered completed if:
        1. It's explicitly in the 'gameover' phase, or
        2. It hasn't received updates in the last 10 minutes
        
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
