"""
Gun weapon analysis for CounterTrak.

Thin wrapper over the shared kill-attribution engine (see kill_attribution.py).
A kill is credited to a gun only when the active firearm actually fired (its
ammo_clip dropped at the kill snapshot) or, as a fallback, when no shot-fired
signal and no grenade was in flight. Kills that the engine attributes to a
grenade are excluded here, so the gun table and the Grenade Impact table never
double-count the same kill.

Output contract (consumed by the player_stats and weapon_analysis views /
templates) is unchanged:
    weapon_id, weapon__name, weapon__type, rounds_used, times_active,
    total_kills, avg_kills_when_active, avg_money
"""
from typing import List, Dict, Any
import logging

from .kill_attribution import build_timelines, attribute_round, FIREARM_TYPES

logger = logging.getLogger(__name__)


def get_weapon_analysis(steam_id: str) -> List[Dict[Any, Any]]:
    """
    Per-firearm usage and ammo-aware kill attribution for a player.

    Args:
        steam_id: The Steam ID of the player to analyze

    Returns:
        A list of per-weapon dicts (see module docstring for keys).
    """
    try:
        kills: Dict[int, int] = {}                  # weapon_id -> attributed gun kills
        rounds_used: Dict[int, int] = {}            # weapon_id -> distinct rounds active
        money_sum: Dict[int, List[float]] = {}      # weapon_id -> [sum_round_avg_money, n_rounds]
        name_type: Dict[int, tuple] = {}            # weapon_id -> (name, type)

        for timeline in build_timelines(steam_id):
            # average money across this round's snapshots
            monies = [s['money'] for s in timeline if s['money'] is not None]
            round_avg_money = (sum(monies) / len(monies)) if monies else 0

            # firearms that were active at any point this round (one count per round)
            active_firearms: Dict[int, tuple] = {}
            for snap in timeline:
                for name, w in snap['weapons'].items():
                    if (w.get('state') == 'active'
                            and w.get('type') in FIREARM_TYPES
                            and w.get('weapon_id') is not None):
                        active_firearms[w['weapon_id']] = (name, w['type'])

            for wid, (name, wtype) in active_firearms.items():
                rounds_used[wid] = rounds_used.get(wid, 0) + 1
                ms = money_sum.setdefault(wid, [0.0, 0])
                ms[0] += round_avg_money
                ms[1] += 1
                name_type[wid] = (name, wtype)

            # gun kills this round (grenade-kind attributions are skipped)
            for attr in attribute_round(timeline):
                if attr['kind'] != 'gun' or attr.get('weapon_id') is None:
                    continue
                wid = attr['weapon_id']
                kills[wid] = kills.get(wid, 0) + attr['kills']
                name_type.setdefault(wid, (attr['weapon'], attr['type']))

        results = []
        for wid in set(list(rounds_used) + list(kills)):
            name, wtype = name_type.get(wid, (None, None))
            ru = rounds_used.get(wid, 0)
            k = kills.get(wid, 0)
            ms = money_sum.get(wid, [0.0, 0])
            results.append({
                'weapon_id': wid,
                'weapon__name': name,
                'weapon__type': wtype,
                'rounds_used': ru,
                'times_active': ru,
                'total_kills': k,
                'avg_kills_when_active': (k / ru) if ru else 0,
                'avg_money': (ms[0] / ms[1]) if ms[1] else 0,
            })
        results.sort(key=lambda r: r['rounds_used'], reverse=True)
        return results

    except Exception as e:
        logger.error(f"Error in weapon analysis for {steam_id}: {str(e)}")
        return []
