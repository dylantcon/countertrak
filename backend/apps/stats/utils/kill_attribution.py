"""
Shared kill-attribution engine for CounterTrak.

CS2's Game State Integration has no killfeed, so every weapon-level kill is
inferred from state deltas over the per-payload snapshots we persist
(PlayerRoundState.round_kills + the PlayerWeapon inventory with ammo_clip /
ammo_reserve). Both the gun analysis and the grenade analysis run off this one
pass so a kill is attributed consistently and never double-counted.

Per kill (a rise in round_kills at a snapshot), in priority order:
  1. GUN  - the active firearm's ammo_clip dropped at this snapshot (a shot was
            fired). The fire delta and the kill delta arrive in the same
            snapshot, so this is the strongest signal. -> high confidence.
  2. GRENADE - no shot was fired AND a lethal grenade (HE/incendiary/molotov)
            was thrown within its fuse/burn window. -> high if a multi-kill in
            one tick, else medium.
  3. GUN fallback - no fire signal and no grenade in flight; credit the active
            firearm anyway (covers the rare case where the ammo delta is masked,
            e.g. a reload in the same one-second snapshot). -> low confidence.
A kill with no active firearm and no grenade evidence (e.g. a knife kill) is
left unattributed rather than guessed.

LIMITATIONS (all from GSI + whole-second snapshot resolution): throw/switch/
fire/detonation inside the same second collapse and cannot be ordered, so a
grenade kill where the player also fired in that second is read as a gun kill.
True per-kill weapons would require demo (.dem) parsing.
"""
from django.db import connection
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)

# grenades that can actually get a kill
LETHAL_GRENADES = {'weapon_hegrenade', 'weapon_incgrenade', 'weapon_molotov'}

# seconds after a throw within which a kill may still be credited to it
# (padded for whole-second snapshot resolution; fire grenades burn longer)
THROW_WINDOW = {
    'weapon_hegrenade': 3,
    'weapon_incgrenade': 9,
    'weapon_molotov': 9,
}

# weapon types that fire bullets (so an ammo_clip drop is a "shot fired" signal)
FIREARM_TYPES = {'Pistol', 'Shotgun', 'Submachine Gun', 'Rifle', 'SniperRifle', 'Machine Gun'}


def _recent_lethal_throw(recent_throws, ts):
    """Most recently thrown lethal grenade still inside its window at time ts."""
    best = None
    best_ts = None
    for ev in recent_throws:
        window = THROW_WINDOW.get(ev['name'], 0)
        if 0 <= ts - ev['ts'] <= window:
            if best_ts is None or ev['ts'] >= best_ts:
                best_ts = ev['ts']
                best = ev['name']
    return best


def attribute_round(timeline: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Attribute every kill in a single (match, round). Pure function - no DB - so
    it is unit-testable directly.

    Args:
        timeline: snapshots for one round ordered by timestamp, each:
            {
              'ts': int, 'round_kills': int, 'money': int|None,
              'weapons': { name: {'weapon_id': int|None, 'type': str, 'state': str,
                                  'ammo_clip': int|None, 'ammo_reserve': int|None} }
            }

    Returns:
        One entry per credited kill batch:
            {'weapon': name, 'weapon_id': int|None, 'type': str|None,
             'kills': int, 'kind': 'gun'|'grenade', 'confidence': 'high'|'medium'|'low'}
    """
    out: List[Dict[str, Any]] = []
    prev_kills = 0
    prev_reserve: Dict[str, int] = {}
    prev_present = set()
    last_clip: Dict[str, int] = {}
    recent_throws: List[Dict[str, Any]] = []

    for snap in timeline:
        ts = snap['ts']
        weapons = snap['weapons']

        # --- detect grenade throws (inventory shrank or reserve dropped) ---
        for name in LETHAL_GRENADES:
            had = name in prev_present
            have = name in weapons
            prev_r = prev_reserve.get(name)
            cur_r = weapons.get(name, {}).get('ammo_reserve') if have else None
            thrown = 0
            if had and not have:
                thrown = prev_r if (prev_r and prev_r > 0) else 1
            elif had and have and prev_r is not None and cur_r is not None and cur_r < prev_r:
                thrown = prev_r - cur_r
            for _ in range(thrown):
                recent_throws.append({'ts': ts, 'name': name})

        # --- active weapon + "did it fire" (only the active gun can fire) ---
        active_name, active = None, None
        for name, w in weapons.items():
            if w.get('state') == 'active':
                active_name, active = name, w
        fired = False
        if active and active.get('type') in FIREARM_TYPES:
            clip = active.get('ammo_clip')
            if clip is not None and active_name in last_clip and clip < last_clip[active_name]:
                fired = True

        # --- attribute new kills at this snapshot ---
        kills = snap['round_kills'] - prev_kills
        if kills > 0:
            grenade = _recent_lethal_throw(recent_throws, ts)
            active_is_gun = bool(active) and active.get('type') in FIREARM_TYPES
            if fired:
                out.append({'weapon': active_name, 'weapon_id': active.get('weapon_id'),
                            'type': active.get('type'), 'kills': kills,
                            'kind': 'gun', 'confidence': 'high'})
            elif grenade is not None:
                out.append({'weapon': grenade, 'weapon_id': weapons.get(grenade, {}).get('weapon_id'),
                            'type': 'Grenade', 'kills': kills, 'kind': 'grenade',
                            'confidence': 'high' if kills >= 2 else 'medium'})
            elif active_is_gun:
                out.append({'weapon': active_name, 'weapon_id': active.get('weapon_id'),
                            'type': active.get('type'), 'kills': kills,
                            'kind': 'gun', 'confidence': 'low'})
            # else: no firearm + no grenade evidence (e.g. knife) -> unattributed

        # --- roll state forward ---
        prev_kills = snap['round_kills']
        prev_present = set(weapons.keys())
        for name in LETHAL_GRENADES:
            if name in weapons:
                prev_reserve[name] = weapons[name].get('ammo_reserve')
        for name, w in weapons.items():
            clip = w.get('ammo_clip')
            if clip is not None:
                last_clip[name] = clip

    return out


def count_throws(timeline: List[Dict[str, Any]]) -> Dict[str, int]:
    """Count lethal-grenade throws in a round (inventory / ammo_reserve deltas)."""
    throws: Dict[str, int] = {}
    prev_reserve: Dict[str, int] = {}
    prev_present = set()
    for snap in timeline:
        weapons = snap['weapons']
        for name in LETHAL_GRENADES:
            had = name in prev_present
            have = name in weapons
            prev_r = prev_reserve.get(name)
            cur_r = weapons.get(name, {}).get('ammo_reserve') if have else None
            if had and not have:
                throws[name] = throws.get(name, 0) + (prev_r if (prev_r and prev_r > 0) else 1)
            elif had and have and prev_r is not None and cur_r is not None and cur_r < prev_r:
                throws[name] = throws.get(name, 0) + (prev_r - cur_r)
        prev_present = set(weapons.keys())
        for name in LETHAL_GRENADES:
            if name in weapons:
                prev_reserve[name] = weapons[name].get('ammo_reserve')
    return throws


def build_timelines(steam_id: str) -> List[List[Dict[str, Any]]]:
    """Fetch a player's snapshots and group them into ordered per-round timelines."""
    rounds: Dict[Any, Dict[int, Dict[str, Any]]] = {}

    # round_kills + money per snapshot (one PRS row per player per snapshot)
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT match_id, round_number,
                   EXTRACT(EPOCH FROM state_timestamp)::bigint AS ts,
                   MAX(round_kills) AS round_kills,
                   MAX(money) AS money
            FROM stats_playerroundstate
            WHERE steam_account_id = %s
            GROUP BY match_id, round_number, state_timestamp
            ORDER BY match_id, round_number, ts
            """,
            [steam_id]
        )
        for match_id, rnd, ts, rk, money in cursor.fetchall():
            rounds.setdefault((match_id, rnd), {})[ts] = {
                'round_kills': rk, 'money': money, 'weapons': {}
            }

    # weapon inventory per snapshot
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT pw.match_id, pw.round_number,
                   EXTRACT(EPOCH FROM pw.state_timestamp)::bigint AS ts,
                   w.weapon_id, w.name, w.type, pw.state, pw.ammo_clip, pw.ammo_reserve
            FROM stats_playerweapon pw
            JOIN stats_weapon w ON pw.weapon_id = w.weapon_id
            WHERE pw.steam_account_id = %s
            ORDER BY pw.match_id, pw.round_number, ts
            """,
            [steam_id]
        )
        for match_id, rnd, ts, wid, name, wtype, state, clip, reserve in cursor.fetchall():
            round_map = rounds.setdefault((match_id, rnd), {})
            snap = round_map.setdefault(ts, {'round_kills': 0, 'money': None, 'weapons': {}})
            snap['weapons'][name] = {
                'weapon_id': wid, 'type': wtype, 'state': state,
                'ammo_clip': clip, 'ammo_reserve': reserve,
            }

    timelines = []
    for snaps in rounds.values():
        timelines.append([
            {'ts': ts, 'round_kills': s['round_kills'], 'money': s['money'], 'weapons': s['weapons']}
            for ts, s in sorted(snaps.items())
        ])
    return timelines
