"""
Estimated grenade usage and kill attribution for CounterTrak.

Thin wrapper over the shared kill-attribution engine (see kill_attribution.py),
which infers grenade kills from inventory + ammo deltas because CS2's GSI has no
killfeed. This module just aggregates the grenade-kind attributions and the
(exactly tracked) throw counts into per-grenade totals for display.
"""
from typing import List, Dict, Any
import logging

from .kill_attribution import build_timelines, attribute_round, count_throws

logger = logging.getLogger(__name__)


def get_grenade_analysis(steam_id: str) -> List[Dict[Any, Any]]:
    """
    Estimate per-grenade usage and kills for a player across all matches.

    Returns a list of dicts, one per lethal grenade type used:
        {
          'grenade': 'hegrenade',     # display name (weapon_ prefix stripped)
          'thrown': int,              # exactly-tracked throws
          'est_kills': int,           # inferred kills (all confidences)
          'high_conf_kills': int,     # subset from multi-kill ticks
          'kills_per_throw': float,
        }
    """
    try:
        agg: Dict[str, Dict[str, Any]] = {}

        for timeline in build_timelines(steam_id):
            for name, throw_count in count_throws(timeline).items():
                bucket = agg.setdefault(name, {'thrown': 0, 'est_kills': 0, 'high_conf_kills': 0})
                bucket['thrown'] += throw_count

            for attr in attribute_round(timeline):
                if attr['kind'] != 'grenade':
                    continue
                bucket = agg.setdefault(attr['weapon'], {'thrown': 0, 'est_kills': 0, 'high_conf_kills': 0})
                bucket['est_kills'] += attr['kills']
                if attr['confidence'] == 'high':
                    bucket['high_conf_kills'] += attr['kills']

        results = []
        for name, b in agg.items():
            thrown = b['thrown']
            results.append({
                'grenade': name[len('weapon_'):] if name.startswith('weapon_') else name,
                'thrown': thrown,
                'est_kills': b['est_kills'],
                'high_conf_kills': b['high_conf_kills'],
                'kills_per_throw': round(b['est_kills'] / thrown, 2) if thrown else 0.0,
            })
        results.sort(key=lambda r: (r['est_kills'], r['thrown']), reverse=True)
        return results

    except Exception as e:
        logger.error(f"Error in grenade analysis for {steam_id}: {str(e)}")
        return []
