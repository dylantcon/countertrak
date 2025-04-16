# gsi/django_integration.py
import os
import django
import logging
from datetime import datetime
from asgiref.sync import sync_to_async

# Configure Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'countertrak.settings')
django.setup()

# Now we can import Django models
from apps.matches.models import Match, Round
from apps.stats.models import PlayerRoundState, PlayerWeapon, PlayerMatchStat, Weapon
from apps.accounts.models import SteamAccount

@sync_to_async
def create_or_update_match(match_state):
    """Create or update Match record from GSI match state"""
    try:
        match, created = Match.objects.update_or_create(
            match_id=match_state.match_id,
            defaults={
                'game_mode': match_state.mode,
                'map_name': match_state.map_name,
                'start_timestamp': datetime.fromtimestamp(match_state.timestamp),
                'team_ct_score': match_state.team_ct_score,
                'team_t_score': match_state.team_t_score,
                'rounds_played': match_state.round,
            }
        )
        return match, created
    except Exception as e:
        logging.error(f"Error creating/updating match: {str(e)}")
        return None, False

@sync_to_async
def create_or_update_round(match_id, round_number, phase, winning_team=None, win_condition=None):
    """Create or update round record"""
    try:
        match = Match.objects.get(match_id=match_id)
        round_obj, created = Round.objects.update_or_create(
            match=match,
            round_number=round_number,
            defaults={
                'phase': phase,
                'winning_team': winning_team,
                'win_condition': win_condition
            }
        )
        return round_obj, created
    except Match.DoesNotExist:
        logging.error(f"Match {match_id} not found when creating round")
        return None, False
    except Exception as e:
        logging.error(f"Error creating/updating round: {str(e)}")
        return None, False

@sync_to_async
def create_or_update_player_state(match_id, round_number, player_state):
    """Create or update player state for a round"""
    try:
        # Get or create steam account
        steam_account, _ = SteamAccount.objects.get_or_create(
            steam_id=player_state.steam_id,
            defaults={
                'player_name': player_state.name, 
                'auth_token': SteamAccount(steam_id=player_state.steam_id).generate_auth_token()
            }
        )
        
        # Get match
        match = Match.objects.get(match_id=match_id)
        
        # Update player round state
        state, created = PlayerRoundState.objects.update_or_create(
            match=match,
            round_number=round_number,
            steam_account=steam_account,
            defaults={
                'health': player_state.health,
                'armor': player_state.armor,
                'money': player_state.money,
                'equip_value': player_state.equip_value,
                'round_kills': player_state.round_kills,
            }
        )
        
        # Update player weapons
        for weapon_slot, weapon_state in player_state.weapons.items():
            weapon, _ = Weapon.objects.get_or_create(
                weapon_id=int(weapon_slot) if weapon_slot.isdigit() else 0,
                defaults={
                    'name': weapon_state.name,
                    'type': weapon_state.type,
                    'max_clip': weapon_state.ammo_clip_max
                }
            )
            
            PlayerWeapon.objects.update_or_create(
                player_round_state=state,
                weapon=weapon,
                defaults={
                    'state': weapon_state.state,
                    'ammo_clip': weapon_state.ammo_clip,
                    'ammo_reserve': weapon_state.ammo_reserve,
                    'paintkit': weapon_state.paintkit
                }
            )
        
        # Update player match stats
        PlayerMatchStat.objects.update_or_create(
            steam_account=steam_account,
            match=match,
            defaults={
                'kills': player_state.match_kills,
                'deaths': player_state.match_deaths,
                'assists': player_state.match_assists,
                'mvps': player_state.match_mvps,
                'score': player_state.match_score
            }
        )
        
        return state
    except Exception as e:
        logging.error(f"Error creating/updating player state: {str(e)}")
        return None
