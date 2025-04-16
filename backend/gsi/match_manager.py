"""
CounterTrak Match Manager

Manages active matches and routes game state payloads to the appropriate
match processors. Serves as the central coordination point for all game
state data flowing through the system.
"""

from gsi.logging_service import match_manager_logger as logger, log_to_file
from gsi.utils import extract_base_match_id, generate_match_id
import asyncio
from typing import Dict, Optional, List
import json

from gsi.match_processor import MatchProcessor

class MatchManager:
    """
    Manages multiple concurrent CS2 matches and routes payloads
    to the appropriate match processor.
    """
    
    def __init__(self):
        """
        Initialize the match manager with an empty dictionary of match processors.
        """
        # dictionary to store active match processors
        # key: match_id, value: matchprocessor instance
        self.match_processors: Dict[str, MatchProcessor] = {}
        
        # lock for thread-safe match processor creation
        self.lock = asyncio.Lock()
        
        logger.info("Match Manager initialized")

    def print_payload(self, payload, indent_level=0):
        """
        Recursively print a nested payload structure for debugging.
        
        Args:
            payload: Dictionary or JSON-like structure to print
            indent_level: Current indentation level (increases with depth)
        """
        if not isinstance(payload, dict):
            logger.warning(f"Payload is not a dictionary: {payload}")
            return
            
        for key, value in payload.items():
            indent_str = ' ' * indent_level
            if not isinstance(value, dict):
                # for non-dictionary values, print key-value pair
                logger.warning(f"{indent_str}{key}: {value}")
            else:
                # for nested dictionaries, print key and recurse
                logger.warning(f"{indent_str}{key}:")
                self.print_payload(value, indent_level + 2)

    async def process_payload(self, payload: Dict) -> None:
        """
        Process a GSI payload by routing it to the appropriate match processor.
        
        This method:
        1. Extracts the match identifier from the payload
        2. Creates a new match processor if this is a new match
        3. Routes the payload to the correct match processor
        
        Args:
            payload: The GSI payload from CS2
        """
        try:
            # extract base_match id using provider.steamid (game client owner)
            base_match_id = self._extract_match_id(payload)
            
            if not base_match_id:
                if self.is_menu_payload(payload):
                    logger.info(f"Player {payload['player']['name']} is in the lobby.")
                else:
                    logger.warning("Could not extract base_match_ID from this payload:")
                    self.print_payload(payload)
                return None

            # extract owner and player steamids for ownership context
            owner_steam_id = payload.get('provider', {}).get('steamid')
            player_steam_id = payload.get('player', {}).get('steamid')
            player_name = payload.get('player', {}).get('name', 'unknown')

            # determine if owner is playing or spectating
            is_owner_playing = (owner_steam_id == player_steam_id)

            if not is_owner_playing:
                logger.debug(f"Client {owner_steam_id} is spectating {player_name} ({player_steam_id})")
            
            # get or create the match processor with owner context
            processor = await self._get_or_create_processor(base_match_id, owner_steam_id)
            
            # process the payload
            await processor.process_payload(payload, is_owner_playing)
            
            # cleanup completed matches periodically
            await self._cleanup_completed_matches()
            
        except Exception as e:
            logger.error(f"Error processing payload: {str(e)}")
    
    async def _get_or_create_processor(self, base_match_id: str, owner_steam_id: str) -> MatchProcessor:
        """
        Get an existing match processor or create a new one if it doesn't exist.
        
        Uses an asyncio lock to ensure thread safety when creating new processors.
        
        Args:
            base_match_id: The match identifier (without UUID appended)
            owner_steam_id: The steam ID of the client owner
            
        Returns:
            The match processor for the specified match
        """
        # first check if a processor already exists for this base_match_id
        # this requires modifying how we store procesors (by base_id instead of full_id)
        # or we need to check all processors to see if their base_id matches
        existing_processor = None
        for match_id, processor in self.match_processors.items():
            if processor.base_match_id == base_match_id:
                existing_processor = processor
                break

        if existing_processor:
            return existing_processor

        # if not, acquire lock and check again to avoid race conditions
        async with self.lock:
            for match_id, processor in self.match_processors.items():
                if processor.base_match_id == base_match_id:
                    return processor

            # generate a full match_id with UUID
            full_match_id = generate_match_id(base_match_id)

            # create a new processor with the generated full match_id
            processor = MatchProcessor(base_match_id, full_match_id, owner_steam_id)
            self.match_processors[full_match_id] = processor
            logger.info(f"Created new match processor for match {full_match_id} owned by {owner_steam_id}")

            return processor
    
    def _extract_match_id(self, payload: Dict) -> Optional[str]:
        """
        Extract the match identifier from a GSI payload. Use provider.steamid
        rather than player.steamid, to prevent payload processing for clients
        that aren't of interest (spectated players, other than our client).
        
        The match ID is constructed from:
        1. Map name
        2. Game mode
        3. Steam ID of the player
        
        This ensures a stable identifier for the entire match duration.
        Creation is handled by gsi.utils.extract_base_match_id(payload)
        
        Args:
            payload: The GSI payload
            
        Returns:
            The match identifier, or None if it couldn't be extracted
        """
        return extract_base_match_id(payload)
    
    async def _cleanup_completed_matches(self) -> None:
        """
        Periodically clean up completed matches to free up resources.
        
        A match is considered completed if it's in the 'gameover' phase
        or if it hasn't received updates in a certain period.
        """
        # list of match ids to remove
        to_remove = []
        
        # check each match processor for completion
        for match_id, processor in self.match_processors.items():
            if processor.is_match_completed():
                to_remove.append(match_id)
        
        # remove completed matches
        if to_remove:
            async with self.lock:
                for match_id in to_remove:
                    if match_id in self.match_processors:
                        del self.match_processors[match_id]
                        logger.info(f"Removed completed match {match_id}")
    
    def get_active_match_count(self) -> int:
        """
        Get the number of active matches currently being processed.
        
        Returns:
            The number of active matches
        """
        return len(self.match_processors)
    
    def get_match_stats(self) -> List[Dict]:
        """
        Get statistics for all active matches.
        
        Returns:
            A list of dictionaries containing match statistics
        """
        return [
            {
                "match_id": match_id,
                "map": processor.get_map_name(),
                "mode": processor.get_game_mode(),
                "phase": processor.get_match_phase(),
                "round": processor.get_current_round(),
                "score_ct": processor.get_ct_score(),
                "score_t": processor.get_t_score(),
                "player_count": processor.get_player_count()
            }
            for match_id, processor in self.match_processors.items()
        ]

    def is_menu_payload(self, payload) -> bool:
        if type(payload) is not dict:
            return False
        if 'player' not in payload:
            return False
        if 'activity' not in payload['player']:
            return False
        return payload['player']['activity'] == 'menu'
