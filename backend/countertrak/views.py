from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count, Avg
from apps.matches.models import Match
from apps.stats.models import PlayerMatchStat, PlayerRoundState
from apps.accounts.models import SteamAccount

def landing(request):
    """Landing page for unauthenticated users"""
    if request.user.is_authenticated:
        return dashboard(request)
    
    # Get some general stats for the landing page
    total_matches = Match.objects.count()
    total_players = SteamAccount.objects.count()
    total_kills = PlayerMatchStat.objects.aggregate(Sum('kills'))['kills__sum'] or 0
    
    context = {
        'total_matches': total_matches,
        'total_players': total_players,
        'total_kills': total_kills,
    }
    
    return render(request, 'landing.html', context)

@login_required
def dashboard(request):
    """Main dashboard for authenticated users"""
    # Get user's Steam accounts
    steam_accounts = SteamAccount.objects.filter(user=request.user)
    
    # If user has linked Steam accounts, get their stats
    user_stats = None
    recent_matches = []
    
    if steam_accounts.exists():
        # Get all matches for all of the user's accounts
        user_match_stats = PlayerMatchStat.objects.filter(
            steam_account__in=steam_accounts
        )
        
        if user_match_stats.exists():
            # Calculate user stats
            user_stats = {
                'total_matches': user_match_stats.count(),
                'total_kills': user_match_stats.aggregate(Sum('kills'))['kills__sum'] or 0,
                'total_deaths': user_match_stats.aggregate(Sum('deaths'))['deaths__sum'] or 0,
                'total_assists': user_match_stats.aggregate(Sum('assists'))['assists__sum'] or 0,
                'total_mvps': user_match_stats.aggregate(Sum('mvps'))['mvps__sum'] or 0,
                'avg_kills': user_match_stats.aggregate(Avg('kills'))['kills__avg'] or 0,
            }
            
            # Calculate K/D ratio
            if user_stats['total_deaths'] > 0:
                user_stats['kd_ratio'] = round(user_stats['total_kills'] / user_stats['total_deaths'], 2)
            else:
                user_stats['kd_ratio'] = user_stats['total_kills']
            
            # Get recent matches
            recent_matches = user_match_stats.order_by('-match__start_timestamp')[:5]
    
    # Get system-wide stats
    total_matches = Match.objects.count()
    recent_system_matches = Match.objects.order_by('-start_timestamp')[:5]
    
    context = {
        'steam_accounts': steam_accounts,
        'user_stats': user_stats,
        'recent_matches': recent_matches,
        'total_matches': total_matches,
        'recent_system_matches': recent_system_matches,
    }
    
    return render(request, 'dashboard.html', context)

def setup_guide(request):
    """Setup guide for new users"""
    return render(request, 'setup_guide.html')