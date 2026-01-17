# apps/matches/serializers.py
from rest_framework import serializers
from .models import Match, Round

class RoundSerializer(serializers.ModelSerializer):
    class Meta:
        model = Round
        fields = ['round_number', 'phase', 'timestamp', 'winning_team', 'win_condition']

class MatchSerializer(serializers.ModelSerializer):
    rounds = RoundSerializer(many=True, read_only=True)
    
    class Meta:
        model = Match
        fields = ['match_id', 'map_name', 'game_mode', 'start_timestamp', 
                 'end_timestamp', 'rounds_played', 'team_ct_score', 
                 'team_t_score', 'rounds']
