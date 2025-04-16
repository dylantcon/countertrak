# apps/stats/views.py
from django.shortcuts import render
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Avg, Sum, Count, F, Q, Case, When, Value, FloatField
from django.db.models.functions import Coalesce

from .models import PlayerMatchStat, PlayerRoundState, PlayerWeapon, Weapon
from .serializers import PlayerMatchStatSerializer, WeaponSerializer
from apps.matches.models import Match

class WeaponViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Weapon.objects.all()
    serializer_class = WeaponSerializer

class PlayerMatchStatViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = PlayerMatchStat.objects.all()
    serializer_class = PlayerMatchStatSerializer
    filterset_fields = ['steam_account', 'match']

class PlayerRoundStateViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = PlayerRoundState.objects.all()
    
    def get_queryset(self):
        queryset = PlayerRoundState.objects.all()
        match_id = self.request.query_params.get('match', None)
        steam_id = self.request.query_params.get('steam_account', None)
        
        if match_id:
            queryset = queryset.filter(match__match_id=match_id)
        if steam_id:
            queryset = queryset.filter(steam_account__steam_id=steam_id)
            
        return queryset

class AnalyticsViewSet(viewsets.ViewSet):
    """
    ViewSet for advanced analytics endpoints
    """
    
    @action(detail=False, methods=['get'])
    def weapon_performance(self, request):
        """Analyze weapon performance across maps"""
        steam_id = request.query_params.get('steam_id', None)
        if not steam_id:
            return Response({"error": "steam_id parameter is required"}, 
                           status=status.HTTP_400_BAD_REQUEST)
        
        # Example complex query - we'll implement the full version later
        # This is just a placeholder to demonstrate the structure
        weapon_stats = PlayerWeapon.objects.filter(
            player_round_state__steam_account__steam_id=steam_id
        ).values(
            'weapon__name', 
            'player_round_state__match__map_name'
        ).annotate(
            usage_count=Count('id'),
            # Additional analytics will go here
        )
        
        return Response(weapon_stats)
    
    @action(detail=False, methods=['get'])
    def economic_analysis(self, request):
        """Analyze economic decisions and their impact"""
        # Placeholder for economic analysis endpoint
        return Response({"message": "Economic analysis endpoint"})
    
    @action(detail=False, methods=['get'])
    def map_performance(self, request):
        """Analyze performance per map"""
        # Placeholder for map performance endpoint
        return Response({"message": "Map performance endpoint"})
