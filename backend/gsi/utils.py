# backend/gsi/utils.py
import uuid
from typing import Dict, Optional, Tuple

def extract_base_match_id(payload: Dict) -> Optional[str]:
    """
    Extract the base match identifier from a GSI payload.
    
    Args:
        payload: The GSI payload
        
    Returns:
        Base match identifier string or None if extraction failed
    """
    try:
        if 'map' not in payload or 'provider' not in payload:
            return None
            
        map_data = payload['map']
        provider_data = payload['provider']
        
        # Extract stable components
        map_name = map_data.get('name', 'unknown_map')
        game_mode = map_data.get('mode', 'unknown_mode')
        owner_steam_id = provider_data.get('steamid', 'unknown_player')
        
        # Create a stable match identifier base
        return f"{map_name}_{game_mode}_{owner_steam_id}"
        
    except Exception:
        return None

def generate_match_id(base_id: str) -> str:
    """
    Generate a unique match ID by appending a UUID to the base ID.
    
    Args:
        base_id: The base match identifier
        
    Returns:
        Complete unique match ID with UUID
    """
    return f"{base_id}_{str(uuid.uuid4())}"

def parse_match_id(match_id: str) -> Tuple[str, Optional[str]]:
    """
    Parse a match ID into its base components and UUID.
    
    Args:
        match_id: The match ID to parse
        
    Returns:
        Tuple of (base_id, uuid_string)
    """
    components = match_id.split('_')
    
    # Check if the match_id has a UUID component
    if len(components) > 3:
        # The last component should be the UUID
        uuid_part = components[-1]
        base_id = '_'.join(components[:-1])
        return base_id, uuid_part
        
    # No UUID component found
    return match_id, None
