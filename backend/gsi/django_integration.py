# gsi/django_integration.py
import os
import django
import logging
from asgiref.sync import sync_to_async

# Configure Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'countertrak.settings')
django.setup()

# Now we can import Django models
from apps.matches.models import Match, Round
from apps.stats.models import PlayerRoundState, PlayerWeapon, PlayerMatchStat, Weapon
from apps.accounts.models import SteamAccount

async def create_or_update_match(match_state):
    """Create or update Match record from GSI match state"""
    @sync_to_async
    def db_operation():
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
    
    return await db_operation()

async def create_or_update_player_state(match_id, round_number, player_state):
    """Create or update player state for a round"""
    @sync_to_async
    def db_operation():
        # Get or create steam account
        steam_account, _ = SteamAccount.objects.get_or_create(
            steam_id=player_state.steam_id,
            defaults={'player_name': player_state.name, 'user': None}
        )
        
        # Update player round state
        state, created = PlayerRoundState.objects.update_or_create(
            match_id=match_id,
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
                weapon_id=int(weapon_slot),
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
        
        return state
    
    return await db_operation()
