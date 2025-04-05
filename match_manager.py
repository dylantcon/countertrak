"""
CounterTrak Match Manager

Manages active matches and routes game state payloads to the appropriate
match processors. Serves as the central coordination point for all game
state data flowing through the system.
"""

import asyncio
import logging
import uuid
from typing import Dict, Optional, List
import json

from match_processor import MatchProcessor

class MatchManager:
    """
    Manages multiple concurrent CS2 matches and routes payloads
    to the appropriate match processor.
    """
    
    def __init__(self):
        """
        Initialize the match manager with an empty dictionary of match processors.
        """
        # Dictionary to store active match processors
        # Key: match_id, Value: MatchProcessor instance
        self.match_processors: Dict[str, MatchProcessor] = {}
        
        # Lock for thread-safe match processor creation
        self.lock = asyncio.Lock()
        
        logging.info("Match Manager initialized")
    
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
            match_id = self._extract_match_id(payload)
            
            if not match_id:
                logging.warning("Could not extract match ID from payload")
                return
            
            # Get or create the match processor
            processor = await self._get_or_create_processor(match_id)
            
            # Process the payload
            await processor.process_payload(payload)
            
            # Cleanup completed matches periodically
            await self._cleanup_completed_matches()
            
        except Exception as e:
            logging.error(f"Error processing payload: {str(e)}")
    
    async def _get_or_create_processor(self, match_id: str) -> MatchProcessor:
        """
        Get an existing match processor or create a new one if it doesn't exist.
        
        Uses an asyncio lock to ensure thread safety when creating new processors.
        
        Args:
            match_id: The match identifier
            
        Returns:
            The match processor for the specified match
        """
        # First check if the processor already exists (fast path)
        if match_id in self.match_processors:
            return self.match_processors[match_id]
        
        # If not, acquire the lock and check again (to avoid race conditions)
        async with self.lock:
            if match_id in self.match_processors:
                return self.match_processors[match_id]
            
            # Create a new processor
            processor = MatchProcessor(match_id)
            self.match_processors[match_id] = processor
            logging.info(f"Created new match processor for match {match_id}")
            
            return processor
    
    def _extract_match_id(self, payload: Dict) -> Optional[str]:
        """
        Extract the match identifier from a GSI payload.
        
        The match ID is constructed from:
        1. Map name
        2. Game mode
        3. Steam ID of the player
        
        This ensures a stable identifier for the entire match duration.
        
        Args:
            payload: The GSI payload
            
        Returns:
            The match identifier, or None if it couldn't be extracted
        """
        try:
            if 'map' not in payload or 'player' not in payload:
                return None
                
            map_data = payload['map']
            player_data = payload['player']
            
            # Extract stable components
            map_name = map_data.get('name', 'unknown_map')
            game_mode = map_data.get('mode', 'unknown_mode')
            steam_id = player_data.get('steamid', 'unknown_player')
            
            # Create a stable match identifier that won't change during the match
            match_id = f"{map_name}_{game_mode}_{steam_id}"
            
            return match_id
            
        except Exception as e:
            logging.error(f"Error extracting match ID: {str(e)}")
            return None
    
    async def _cleanup_completed_matches(self) -> None:
        """
        Periodically clean up completed matches to free up resources.
        
        A match is considered completed if it's in the 'gameover' phase
        or if it hasn't received updates in a certain period.
        """
        # List of match IDs to remove
        to_remove = []
        
        # Check each match processor for completion
        for match_id, processor in self.match_processors.items():
            if processor.is_match_completed():
                to_remove.append(match_id)
        
        # Remove completed matches
        if to_remove:
            async with self.lock:
                for match_id in to_remove:
                    if match_id in self.match_processors:
                        del self.match_processors[match_id]
                        logging.info(f"Removed completed match {match_id}")
    
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
