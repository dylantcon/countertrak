from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, Sum, F, Q
from .models import PlayerMatchStat, PlayerRoundState, PlayerWeapon, Weapon
from apps.accounts.models import SteamAccount
from apps.matches.models import Match, Round

@login_required
def player_stats(request, steam_id=None):
    """Show detailed statistics for a player"""
    # If steam_id not provided, use the first linked account of the user
    if not steam_id:
        steam_accounts = SteamAccount.objects.filter(user=request.user)
        if not steam_accounts.exists():
            return render(request, 'stats/no_accounts.html')
        steam_id = steam_accounts.first().steam_id
    
    # Get the requested steam account
    steam_account = get_object_or_404(SteamAccount, steam_id=steam_id)
    
    # If this is not the user's account and not a public profile, deny access
    # (For now, all accounts are accessible)
    
    # Get basic stats
    match_stats = PlayerMatchStat.objects.filter(steam_account=steam_account)
    total_matches = match_stats.count()
    total_kills = match_stats.aggregate(Sum('kills'))['kills__sum'] or 0
    total_deaths = match_stats.aggregate(Sum('deaths'))['deaths__sum'] or 0
    total_assists = match_stats.aggregate(Sum('assists'))['assists__sum'] or 0
    total_mvps = match_stats.aggregate(Sum('mvps'))['mvps__sum'] or 0
    
    # Calculate KD ratio, handling division by zero
    kd_ratio = round(total_kills / total_deaths, 2) if total_deaths > 0 else total_kills
    
    # Get recent matches
    recent_matches = match_stats.order_by('-match__start_timestamp')[:5]
    
    # Get weapon effectiveness (Using performance pattern recognition)
    weapon_stats = PlayerWeapon.objects.filter(
        player_round_state__steam_account=steam_account,
        state='active'
    ).values(
        'weapon__name', 'weapon__type'
    ).annotate(
        times_used=Count('weapon'),
        total_kills=Sum('player_round_state__round_kills'),
        avg_kills=Avg('player_round_state__round_kills')
    ).order_by('-avg_kills')
    
    context = {
        'steam_account': steam_account,
        'total_matches': total_matches,
        'total_kills': total_kills,
        'total_deaths': total_deaths,
        'total_assists': total_assists,
        'total_mvps': total_mvps,
        'kd_ratio': kd_ratio,
        'recent_matches': recent_matches,
        'weapon_stats': weapon_stats,
    }
    
    return render(request, 'stats/player_stats.html', context)

@login_required
def match_detail(request, match_id):
    """Show detailed statistics for a specific match"""
    match = get_object_or_404(Match, match_id=match_id)
    
    # Get players in this match
    player_stats = PlayerMatchStat.objects.filter(match=match).order_by('-score')
    
    # Get round data
    rounds = Round.objects.filter(match=match).order_by('round_number')
    
    # Get team compositions and scores
    ct_players = player_stats.filter(steam_account__playerroundstate__team='CT').distinct()
    t_players = player_stats.filter(steam_account__playerroundstate__team='T').distinct()
    
    context = {
        'match': match,
        'player_stats': player_stats,
        'rounds': rounds,
        'ct_players': ct_players,
        't_players': t_players,
    }
    
    return render(request, 'stats/match_detail.html', context)

@login_required
def weapon_analysis(request, steam_id=None):
    """Advanced weapon analysis (Advanced Pattern Recognition)"""
    # If steam_id not provided, use the first linked account of the user
    if not steam_id:
        steam_accounts = SteamAccount.objects.filter(user=request.user)
        if not steam_accounts.exists():
            return render(request, 'stats/no_accounts.html')
        steam_id = steam_accounts.first().steam_id
    
    # Get the requested steam account
    steam_account = get_object_or_404(SteamAccount, steam_id=steam_id)
    
    # Advanced weapon effectiveness analysis
    # This goes beyond simple K/D by analyzing contextual weapon effectiveness
    weapon_analysis = PlayerWeapon.objects.filter(
        player_round_state__steam_account=steam_account
    ).values(
        'weapon__name', 'weapon__type'
    ).annotate(
        times_active=Count('weapon', filter=Q(state='active')),
        times_holstered=Count('weapon', filter=Q(state='holstered')),
        rounds_used=Count('player_round_state', distinct=True),
        total_kills=Sum('player_round_state__round_kills', filter=Q(state='active')),
        avg_kills_when_active=Avg('player_round_state__round_kills', filter=Q(state='active')),
        avg_money=Avg('player_round_state__money'),
    ).filter(
        times_active__gt=0
    ).order_by('-avg_kills_when_active')
    
    # Economic analysis - how does the player's spending correlate with performance?
    economic_data = PlayerRoundState.objects.filter(
        steam_account=steam_account
    ).values(
        'round_number', 'money', 'equip_value'
    ).annotate(
        kills=Sum('round_kills')
    ).order_by('match', 'round_number')
    
    context = {
        'steam_account': steam_account,
        'weapon_analysis': weapon_analysis,
        'economic_data': economic_data,
    }
    
    return render(request, 'stats/weapon_analysis.html', context)

def stats_home(request):
    """Stats homepage with overview of system data"""
    # Get global statistics
    total_matches = Match.objects.count()
    total_players = SteamAccount.objects.count()
    total_rounds = Round.objects.count()
    total_kills = PlayerMatchStat.objects.aggregate(Sum('kills'))['kills__sum'] or 0
    
    # Most popular maps
    popular_maps = Match.objects.values('map_name').annotate(
        count=Count('match_id')
    ).order_by('-count')[:5]
    
    # Most used weapons
    popular_weapons = PlayerWeapon.objects.values('weapon__name').annotate(
        count=Count('id')
    ).order_by('-count')[:5]
    
    # Recent matches
    recent_matches = Match.objects.order_by('-start_timestamp')[:10]
    
    context = {
        'total_matches': total_matches,
        'total_players': total_players,
        'total_rounds': total_rounds,
        'total_kills': total_kills,
        'popular_maps': popular_maps,
        'popular_weapons': popular_weapons,
        'recent_matches': recent_matches,
    }
    
    return render(request, 'stats/stats_home.html', context)
