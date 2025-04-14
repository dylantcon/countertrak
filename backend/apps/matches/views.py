# apps/matches/views.py
from django.shortcuts import render
from rest_framework import viewsets
from .models import Match, Round
from .serializers import MatchSerializer, RoundSerializer

class MatchViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Match.objects.all()
    serializer_class = MatchSerializer
    filterset_fields = ['map_name', 'game_mode']
    search_fields = ['match_id', 'map_name']
