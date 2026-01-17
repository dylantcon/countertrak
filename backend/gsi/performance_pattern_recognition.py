"""
CounterTrak Performance Pattern Recognition Engine

This module implements advanced analytics for player performance data,
analyzing patterns in weapon usage, economic decisions, and round outcomes.
This is the core of CounterTrak's advanced analytics functionality.
"""

import logging
from typing import Dict, List, Tuple, Optional
from django.db.models import Avg, Count, Sum, F, Q, Case, When, Value, IntegerField
from django.db.models.functions import Coalesce

from apps.stats.models import PlayerMatchStat, PlayerRoundState, PlayerWeapon
from apps.matches.models import Match, Round
from apps.accounts.models import SteamAccount

class PerformancePatternRecognition:
    """
    Advanced analytics engine for identifying patterns in player performance.
    
    This class implements the advanced analytics functionality described in the
    project documentation, focusing on Performance Pattern Recognition to provide
    actionable insights about player behavior and effectiveness.
    """
    
    def __init__(self, steam_id: str = None):
        """
        Initialize the analytics engine.
        
        Args:
            steam_id: Optional Steam ID to limit analysis to a specific player
        """
        self.steam_id = steam_id
        self.logger = logging.getLogger(__name__)
    
    def analyze_weapon_effectiveness(self) -> Dict:
        """
        Analyze weapon effectiveness in different contexts.
        
        This method examines how effective different weapons are based on:
        - Economic conditions (full buy, eco, force buy)
        - Map context
        - Team composition
        
        Returns:
            Dictionary containing weapon effectiveness analysis
        """
        query = PlayerWeapon.objects.filter(
            state='active'  # Only analyze weapons when they were actively used
        )
        
        # If steam_id provided, limit to that player
        if self.steam_id:
            query = query.filter(player_round_state__steam_account__steam_id=self.steam_id)
        
        # Get weapon effectiveness grouped by weapon
        weapon_data = query.values(
            'weapon__name', 
            'weapon__type',
            'player_round_state__match__map_name'
        ).annotate(
            times_used=Count('id'),
            total_kills=Sum('player_round_state__round_kills'),
            avg_kills=Avg('player_round_state__round_kills'),
            avg_money=Avg('player_round_state__money'),
            avg_equip_value=Avg('player_round_state__equip_value'),
            eco_rounds=Count(
                'id',
                filter=Q(player_round_state__money__lt=2000)
            ),
            force_rounds=Count(
                'id',
                filter=Q(player_round_state__money__gte=2000, player_round_state__money__lt=4000)
            ),
            full_buy_rounds=Count(
                'id',
                filter=Q(player_round_state__money__gte=4000)
            )
        ).order_by('-avg_kills')
        
        # Process data for easier consumption
        for weapon in weapon_data:
            # Clean up weapon name
            if weapon['weapon__name'].startswith('weapon_'):
                weapon['clean_name'] = weapon['weapon__name'][7:]
            else:
                weapon['clean_name'] = weapon['weapon__name']
            
            # Calculate effectiveness score (custom metric)
            kills = weapon['total_kills'] or 0
            uses = weapon['times_used'] or 1
            equip_value = weapon['avg_equip_value'] or 1
            
            # Higher is better - kills per use per dollar spent
            weapon['effectiveness_score'] = (kills / uses) * 1000 / equip_value
            
            # Economic context effectiveness
            weapon['eco_effectiveness'] = self._calculate_context_effectiveness(
                weapon['eco_rounds'], kills, uses
            )
            
            weapon['force_effectiveness'] = self._calculate_context_effectiveness(
                weapon['force_rounds'], kills, uses
            )
            
            weapon['full_buy_effectiveness'] = self._calculate_context_effectiveness(
                weapon['full_buy_rounds'], kills, uses
            )
        
        return {
            'weapons': list(weapon_data),
            'total_weapons_analyzed': len(weapon_data)
        }
    
    def analyze_economic_patterns(self) -> Dict:
        """
        Analyze economic decision patterns and their impact on performance.
        
        This method identifies patterns in:
        - How money is spent across rounds
        - How equipment value correlates with performance
        - Optimal economic thresholds for different weapons
        
        Returns:
            Dictionary containing economic pattern analysis
        """
        query = PlayerRoundState.objects.all()
        
        # If steam_id provided, limit to that player
        if self.steam_id:
            query = query.filter(steam_account__steam_id=self.steam_id)
        
        # Analyze economic data across rounds
        economic_data = query.values(
            'match__map_name',
            'round_number'
        ).annotate(
            money=Avg('money'),
            equip_value=Avg('equip_value'),
            kills=Avg('round_kills'),
            team_ct_count=Count('id', filter=Q(team='CT')),
            team_t_count=Count('id', filter=Q(team='T'))
        ).order_by('match__map_name', 'round_number')
        
        # Categorize rounds by economic state
        for round_data in economic_data:
            if round_data['equip_value'] < 2000:
                round_data['economic_state'] = 'Eco'
            elif round_data['equip_value'] < 4000:
                round_data['economic_state'] = 'Force Buy'
            else:
                round_data['economic_state'] = 'Full Buy'
        
        # Calculate aggregated statistics by economic state
        eco_stats = {
            'Eco': {'rounds': 0, 'total_kills': 0, 'avg_kills': 0},
            'Force Buy': {'rounds': 0, 'total_kills': 0, 'avg_kills': 0},
            'Full Buy': {'rounds': 0, 'total_kills': 0, 'avg_kills': 0}
        }
        
        for round_data in economic_data:
            state = round_data['economic_state']
            eco_stats[state]['rounds'] += 1
            eco_stats[state]['total_kills'] += round_data['kills'] or 0
        
        # Calculate averages
        for state in eco_stats:
            if eco_stats[state]['rounds'] > 0:
                eco_stats[state]['avg_kills'] = eco_stats[state]['total_kills'] / eco_stats[state]['rounds']
            
            # Calculate effectiveness relative to cost
            if state == 'Eco':
                avg_cost = 1000  # Approximate
            elif state == 'Force Buy':
                avg_cost = 3000  # Approximate
            else:
                avg_cost = 5000  # Approximate
            
            kills = eco_stats[state]['total_kills']
            rounds = eco_stats[state]['rounds'] or 1
            
            # Higher is better - kills per round per dollar spent
            eco_stats[state]['cost_effectiveness'] = (kills / rounds) * 1000 / avg_cost
        
        return {
            'round_data': list(economic_data),
            'economic_stats': eco_stats
        }
    
    def analyze_weapon_sequences(self) -> Dict:
        """
        Analyze patterns in weapon selection sequences across rounds.
        
        This method identifies effective weapon progression patterns,
        considering transitions between different weapon types.
        
        Returns:
            Dictionary containing weapon sequence analysis
        """
        # This would require time series analysis of weapon choices across rounds
        # For now, we'll implement a simplified version
        
        query = PlayerRoundState.objects.all()
        
        # If steam_id provided, limit to that player
        if self.steam_id:
            query = query.filter(steam_account__steam_id=self.steam_id)
        
        # Get weapon sequences by match and round
        sequence_data = query.values(
            'match__match_id',
            'round_number'
        ).order_by(
            'match__match_id',
            'round_number'
        )
        
        # This is a placeholder for more sophisticated sequence analysis
        # In a real implementation, we would track weapon transitions and
        # analyze their effectiveness
        
        return {
            'sequences_analyzed': len(sequence_data),
            'message': 'Weapon sequence analysis requires more data to generate meaningful insights.'
        }
    
    def generate_performance_insights(self) -> Dict:
        """
        Generate actionable performance insights based on all analyses.
        
        This method combines the results of all analysis methods to produce
        a comprehensive set of insights and recommendations.
        
        Returns:
            Dictionary containing performance insights and recommendations
        """
        weapon_analysis = self.analyze_weapon_effectiveness()
        economic_analysis = self.analyze_economic_patterns()
        
        insights = {
            'weapons': [],
            'economic': [],
            'general': []
        }
        
        # Generate weapon insights
        weapons = weapon_analysis.get('weapons', [])
        if weapons:
            # Find best weapon overall
            best_weapon = max(weapons, key=lambda w: w.get('avg_kills', 0))
            insights['weapons'].append({
                'text': f"Your most effective weapon is the {best_weapon.get('clean_name', '')}, averaging {best_weapon.get('avg_kills', 0):.2f} kills per active round.",
                'type': 'strength'
            })
            
            # Find best eco weapon
            eco_weapons = [w for w in weapons if w.get('eco_rounds', 0) >= 3]
            if eco_weapons:
                best_eco = max(eco_weapons, key=lambda w: w.get('eco_effectiveness', 0))
                insights['weapons'].append({
                    'text': f"During eco rounds, consider using the {best_eco.get('clean_name', '')}, which has proven effective for you.",
                    'type': 'recommendation'
                })
            
            # Find best value weapon
            value_weapons = [w for w in weapons if w.get('times_used', 0) >= 5]
            if value_weapons:
                best_value = max(value_weapons, key=lambda w: w.get('effectiveness_score', 0))
                insights['weapons'].append({
                    'text': f"The {best_value.get('clean_name', '')} provides your best value for money based on performance.",
                    'type': 'insight'
                })
            
            # Find weapons that need improvement
            weak_weapons = [w for w in weapons if w.get('times_used', 0) >= 5 and w.get('avg_kills', 0) < 0.3]
            if weak_weapons:
                worst_weapon = min(weak_weapons, key=lambda w: w.get('avg_kills', 0))
                insights['weapons'].append({
                    'text': f"Consider practicing with the {worst_weapon.get('clean_name', '')}, as it currently has lower effectiveness.",
                    'type': 'improvement'
                })
        
        # Generate economic insights
        eco_stats = economic_analysis.get('economic_stats', {})
        if eco_stats:
            # Compare different economic strategies
            best_state = max(eco_stats.keys(), key=lambda k: eco_stats[k].get('cost_effectiveness', 0))
            insights['economic'].append({
                'text': f"{best_state} rounds provide your best return on investment in terms of kills per dollar spent.",
                'type': 'insight'
            })
            
            # Specific advice based on eco performance
            if eco_stats.get('Eco', {}).get('avg_kills', 0) > 0.5:
                insights['economic'].append({
                    'text': "You perform well during eco rounds, indicating good pistol skills and positioning.",
                    'type': 'strength'
                })
            elif eco_stats.get('Eco', {}).get('avg_kills', 0) < 0.2:
                insights['economic'].append({
                    'text': "Focus on improving pistol and SMG effectiveness to boost performance in eco and force-buy rounds.",
                    'type': 'improvement'
                })
        
        # Generate general insights
        insights['general'].append({
            'text': "Continuing to collect match data will provide more precise and personalized insights over time.",
            'type': 'information'
        })
        
        return {
            'weapon_analysis': weapon_analysis,
            'economic_analysis': economic_analysis,
            'insights': insights
        }
    
    def _calculate_context_effectiveness(self, context_rounds: int, total_kills: int, total_uses: int) -> float:
        """
        Calculate weapon effectiveness in a specific context.
        
        Args:
            context_rounds: Number of rounds in the specific context
            total_kills: Total kills with the weapon
            total_uses: Total times the weapon was used
        
        Returns:
            Effectiveness score for the context
        """
        if context_rounds == 0 or total_uses == 0:
            return 0.0
        
        # Estimate kills in this context based on proportion of rounds
        context_ratio = context_rounds / total_uses
        estimated_kills = total_kills * context_ratio
        
        # Calculate effectiveness (kills per round in this context)
        return estimated_kills / context_rounds if context_rounds > 0 else 0.0