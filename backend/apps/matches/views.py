# apps/matches/views.py
from django.shortcuts import render, redirect
from rest_framework import viewsets
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import connection
from .models import Match, Round
from .serializers import MatchSerializer, RoundSerializer

class MatchViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Match.objects.all()
    serializer_class = MatchSerializer
    filterset_fields = ['map_name', 'game_mode']
    search_fields = ['match_id', 'map_name']

@login_required
def delete_match(request, match_id):
    """Delete a match and all associated data"""
    try:
        # Check if the user has permission to delete this match
        # Get the match owner from player match stats
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT sa.user_id 
                FROM stats_playermatchstat pms
                JOIN accounts_steamaccount sa ON pms.steam_account_id = sa.steam_id
                WHERE pms.match_id = %s AND sa.user_id = %s
                LIMIT 1
            """, [match_id, request.user.id])
            
            is_owner = cursor.fetchone() is not None

        # If the user is not the owner and not a superuser, deny access
        if not is_owner and not request.user.is_superuser:
            messages.error(request, "You don't have permission to delete this match.")
            return redirect('dashboard')
            
        # Perform deletion using database connection to handle foreign key cascades
        with connection.cursor() as cursor:
            # Delete in correct order to respect foreign key constraints
            # 1. Delete player weapons
            cursor.execute("DELETE FROM stats_playerweapon WHERE match_id = %s", [match_id])
            weapon_count = cursor.rowcount
            
            # 2. Delete player round states
            cursor.execute("DELETE FROM stats_playerroundstate WHERE match_id = %s", [match_id])
            round_state_count = cursor.rowcount
            
            # 3. Delete player match stats
            cursor.execute("DELETE FROM stats_playermatchstat WHERE match_id = %s", [match_id])
            stats_count = cursor.rowcount
            
            # 4. Delete rounds
            cursor.execute("DELETE FROM matches_round WHERE match_id = %s", [match_id])
            rounds_count = cursor.rowcount
            
            # 5. Finally delete the match
            cursor.execute("DELETE FROM matches_match WHERE match_id = %s", [match_id])
            match_deleted = cursor.rowcount > 0
            
        if match_deleted:
            messages.success(request, f"Match {match_id} deleted successfully with {rounds_count} rounds, {round_state_count} player states, and {weapon_count} weapon records.")
        else:
            messages.error(request, f"Failed to delete match {match_id}.")
            
        # Redirect to referring page or dashboard
        referer = request.META.get('HTTP_REFERER')
        if referer and ('/dashboard/' in referer or '/stats/' in referer):
            return redirect(referer)
        return redirect('dashboard')
            
    except Exception as e:
        messages.error(request, f"Error deleting match: {str(e)}")
        return redirect('dashboard')
