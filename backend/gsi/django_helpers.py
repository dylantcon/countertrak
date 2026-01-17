from asgiref.sync import sync_to_async
from apps.matches.models import Match
from apps.accounts.models import SteamAccount
from datetime import datetime

@sync_to_async
def create_or_update_match(match_state):
    """Create or update Match record from GSI match state"""
    # Parse timestamp from match_id
    _, _, _, timestamp_str = match_state.match_id.rsplit('_', 3)
    timestamp = datetime.fromtimestamp(int(timestamp_str))
    
    match, created = Match.objects.update_or_create(
        match_id=match_state.match_id,
        defaults={
            'game_mode': match_state.mode,
            'map_name': match_state.map_name,
            'start_timestamp': timestamp,
            'team_ct_score': match_state.team_ct_score,
            'team_t_score': match_state.team_t_score,
        }
    )
    return match, created
