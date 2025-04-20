"""
CounterTrak Match Manager

Manages active matches and routes game state payloads to the appropriate
match processors. Serves as the central coordination point for all game
state data flowing through the system. Instantiates MatchProcessors on-
the-fly for any new payloads, by inspecting its member data to see if a
MatchProcessor already exists for a given match_id.
"""

from gsi.logging_service import match_manager_logger as logger
from gsi.utils import extract_base_match_id, generate_match_id
import asyncio
from typing import Dict, Optional, List
import json

from gsi.match_processor import MatchProcessor

class MatchManager:
    """
    Manages multiple concurrent CS2 matches and routes payloads
    to the appropriate match processor.
    
    Responsibilities:
    1. Create and maintain match processors for active matches
    2. Route payloads to the correct match processor
    3. Clean up completed matches
    4. Provide match statistics to external systems
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

    async def route_payload(self, payload: Dict) -> bool:
        """
        Process a GSI payload by routing it to the appropriate match processor.
        
        This method:
        1. Extracts the match identifier from the payload
        2. Creates a new match processor if this is a new match
        3. Routes the payload to the correct match processor
        
        Args:
            payload: The GSI payload from CS2
            
        Returns:
            True if payload was processed, False otherwise
        """
        try:
            # extract base_match id using provider.steamid (game client owner)
            base_match_id = self._extract_match_id(payload)

            if not base_match_id:
                if self.is_menu_payload(payload):
                    player_name = payload.get('player', {}).get('name', 'unknown')
                    logger.debug(f"Player {player_name} is in the lobby menu")
                else:
                    logger.warning("Could not extract base_match_ID from payload")
                    self._debug_log_payload(payload)
                return False

            # extract owner and player steamids for ownership context
            owner_steam_id = payload.get('provider', {}).get('steamid')
            player_steam_id = payload.get('player', {}).get('steamid')
            player_name = payload.get('player', {}).get('name', 'unknown')

            # player ids should be present
            if not owner_steam_id or not player_steam_id:
                logger.warning("Missing steam IDs in payload")
                return False

            # determine if owner is playing or spectating
            is_owner_playing = (owner_steam_id == player_steam_id)

            if not is_owner_playing:
                logger.debug(f"Client {owner_steam_id} is spectating {player_name} ({player_steam_id})")

            # get or create the match processor with owner context
            processor = await self._get_or_create_processor(base_match_id, owner_steam_id)
            if not processor:
                logger.error(f"Failed to create processor for match {base_match_id}")
                return False

            # process the payload
            await processor.handle_payload(payload, is_owner_playing)

            # cleanup completed matches periodically
            await self._cleanup_completed_matches()
            return True

        except Exception as e:
            logger.error(f"Error processing payload: {str(e)}")
            logger.exception(e)
            return False

    async def _get_or_create_processor(self, base_match_id: str, owner_steam_id: str) -> Optional[MatchProcessor]:
        """
        Get an existing match processor or create a new one if it doesn't exist.
        
        Uses an asyncio lock to ensure thread safety when creating new processors.
        
        Args:
            base_match_id: The match identifier (without UUID appended)
            owner_steam_id: The steam ID of the client owner
            
        Returns:
            The match processor for the specified match, or None if creation failed
        """
        # first check if a processor already exists for this base_match_id
        existing_processor = None
        for match_id, processor in self.match_processors.items():
            if processor.base_match_id == base_match_id:
                existing_processor = processor
                break

        if existing_processor:
            return existing_processor

        # if not, acquire lock and check again to avoid race conditions
        async with self.lock:
            # double-check after acquiring lock
            for match_id, processor in self.match_processors.items():
                if processor.base_match_id == base_match_id:
                    return processor

            try:
                # generate a full match_id with uuid
                full_match_id = generate_match_id(base_match_id)

                # create a new processor with the generated full match_id
                processor = MatchProcessor(base_match_id, full_match_id, owner_steam_id)
                self.match_processors[full_match_id] = processor
                logger.info(f"Created new match processor for match {full_match_id} owned by {owner_steam_id}")

                return processor
            except Exception as e:
                logger.error(f"Error creating match processor: {str(e)}")
                logger.exception(e)
                return None

    def _extract_match_id(self, payload: Dict) -> Optional[str]:
        """
        Extract the base match identifier from a GSI payload. Use provider.steamid
        rather than player.steamid, to prevent payload processing for clients
        that aren't of interest (spectated players, other than our client).

        'base' refers to the match_id without UUID appended--this is added when
        appending a MatchProcessor instance to the dictionary stored as member
        data in this class, MatchManager. This is to prevent any potential dict
        key ambiguity when the MatchManager is searching for a pre-existing
        MatchProcessor instance, that may already be handling the payloads for
        a match.

        The base match ID is constructed from:

            1. Map name
            2. Game mode
            3. Steam ID of the player

        This ensures a stable identifier for the entire match duration.
        Creation is handled by gsi.utils.extract_base_match_id(payload)

        Args:
            payload: The GSI payload

        Returns:
            The base match identifier, or None if it couldn't be extracted
        """
        return extract_base_match_id(payload)

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

    async def _cleanup_completed_matches(self) -> None:
        """
        Periodically clean up completed matches to free up resources.
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

    def is_menu_payload(self, payload: Dict) -> bool:
        """
        Check if a payload is from the game menu rather than a match.
        
        Args:
            payload: The GSI payload
            
        Returns:
            True if the payload is from the menu, False otherwise
        """
        if not isinstance(payload, dict):
            return False
        if 'player' not in payload:
            return False
        if 'activity' not in payload['player']:
            return False
        return payload['player']['activity'] == 'menu'
