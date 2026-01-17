from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, Sum, F, Q, Case, When, Value, FloatField, IntegerField
from .models import PlayerMatchStat, PlayerRoundState, PlayerWeapon, Weapon
from .utils.weapon_analyzer import get_weapon_analysis
from apps.accounts.models import SteamAccount
from apps.matches.models import Match, Round

@login_required
def player_stats(request, steam_id=None):
    """Show detailed statistics for a player"""
    # if steam_id not provided, use the first linked account of the user
    if not steam_id:
        steam_accounts = SteamAccount.objects.filter(user=request.user)
        if not steam_accounts.exists():
            return render(request, 'stats/no_accounts.html')
        steam_id = steam_accounts.first().steam_id
    
    # get the requested steam account
    steam_account = get_object_or_404(SteamAccount, steam_id=steam_id)
    
    # get basic stats
    match_stats = PlayerMatchStat.objects.filter(steam_account=steam_account)
    total_matches = match_stats.count()
    total_kills = match_stats.aggregate(Sum('kills'))['kills__sum'] or 0
    total_deaths = match_stats.aggregate(Sum('deaths'))['deaths__sum'] or 0
    total_assists = match_stats.aggregate(Sum('assists'))['assists__sum'] or 0
    total_mvps = match_stats.aggregate(Sum('mvps'))['mvps__sum'] or 0
    
    # calculate kd ratio, handling division by zero
    kd_ratio = round(total_kills / total_deaths, 2) if total_deaths > 0 else total_kills
    
    # get recent matches
    recent_matches = match_stats.order_by('-match__start_timestamp')[:5]
    
    # get weapon effectiveness using our new utility function
    from .utils.weapon_analyzer import get_weapon_analysis
    weapon_stats_raw = get_weapon_analysis(steam_id)
    
    # transform the data to match the expected format for the template
    weapon_stats = []
    for weapon in weapon_stats_raw:
        weapon_stats.append({
            'weapon__name': weapon['weapon__name'],
            'weapon__type': weapon['weapon__type'],
            'times_used': weapon['times_active'],  # map times_active to times_used
            'avg_kills': weapon['avg_kills_when_active']  # map avg_kills_when_active to avg_kills
        })
    
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
    
    # get players in this match
    player_stats = PlayerMatchStat.objects.filter(match=match).order_by('-score')
    
    # get round data
    rounds = Round.objects.filter(match=match).order_by('round_number')
    
    # get team compositions - handle cases where team attribute might not exist
    ct_players = set()
    t_players = set()
    
    for player in player_stats:
        # get the player's team from their most recent round state
        latest_state = PlayerRoundState.objects.filter(
            match=match,
            steam_account=player.steam_account
        ).order_by('-round_number').first()
        
        if latest_state:
            # handle cases where the team attribute might not exist
            try:
                team = latest_state.team
                if team == 'CT':
                    ct_players.add(player.steam_account)
                elif team == 'T':
                    t_players.add(player.steam_account)
            except AttributeError:
                # if team attribute doesn't exist, use default logic
                # we can guess based on other factors or just not assign team
                pass
    
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
    # if steam_id not provided, use the first linked account of the user
    if not steam_id:
        steam_accounts = SteamAccount.objects.filter(user=request.user)
        if not steam_accounts.exists():
            return render(request, 'stats/no_accounts.html')
        steam_id = steam_accounts.first().steam_id
    
    # get the requested steam account
    steam_account = get_object_or_404(SteamAccount, steam_id=steam_id)

    # use weapon_analysis sql query utility function
    weapon_analysis = get_weapon_analysis(steam_id)

    for weapon in weapon_analysis:
        print(
            f"Weapon: {weapon['weapon__name']}, " +
            f"Kills: {weapon.get('total_kills', 0)}, " +
            f"Times active: {weapon['times_active']}"
        )
    
    # economic analysis - how does the player's spending correlate with performance?
    economic_data = PlayerRoundState.objects.filter(
        steam_account=steam_account
    ).values(
        'round_number', 'money', 'equip_value'
    ).annotate(
        kills=Sum('round_kills')  # use sum instead of count for round_kills
    ).order_by('match', 'round_number')
    
    print(f"Economic data count: {len(economic_data)}")
    
    context = {
        'steam_account': steam_account,
        'weapon_analysis': weapon_analysis,
        'economic_data': economic_data,
    }
    
    return render(request, 'stats/weapon_analysis.html', context)

def stats_home(request):
    """Stats homepage with overview of system data"""
    # get global statistics
    total_matches = Match.objects.count()
    total_players = SteamAccount.objects.count()
    total_rounds = Round.objects.count()
    total_kills = PlayerMatchStat.objects.aggregate(Sum('kills'))['kills__sum'] or 0
    
    # most popular maps
    popular_maps = Match.objects.values('map_name').annotate(
        count=Count('match_id')
    ).order_by('-count')[:5]
    
    # most used weapons
    popular_weapons = PlayerWeapon.objects.values('weapon__name').annotate(
        count=Count('id')
    ).order_by('-count')[:5]
    
    # recent matches
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
