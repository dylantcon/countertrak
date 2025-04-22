from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib import messages
from .models import SteamAccount
from .forms import SteamAccountForm

def register(request):
    """Register a new user account"""
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Account created successfully! Please log in.')
            return redirect('login')
    else:
        form = UserCreationForm()
    return render(request, 'accounts/register.html', {'form': form})

@login_required
def profile(request):
    """View user profile with linked Steam accounts"""
    steam_accounts = SteamAccount.objects.filter(user=request.user)
    return render(request, 'accounts/profile.html', {'steam_accounts': steam_accounts})

@login_required
def link_steam(request):
    """Link a Steam account to the user"""
    if request.method == 'POST':
        form = SteamAccountForm(request.POST)
        if form.is_valid():
            steam_account = form.save(commit=False)
            steam_account.user = request.user
            steam_account.save()
            messages.success(request, f'Steam account {steam_account.player_name} linked successfully!')
            return redirect('profile')
    else:
        form = SteamAccountForm()
    return render(request, 'accounts/link_steam.html', {'form': form})

@login_required
def generate_config(request, steam_id):
    """Generate CS2 config file for the specified Steam account"""
    try:
        steam_account = SteamAccount.objects.get(steam_id=steam_id, user=request.user)
        context = {
            'steam_account': steam_account,
            'host': request.get_host().split(':')[0]  # remove port if present
        }
        response = render(request, 'accounts/gsi_config.cfg', context, content_type='text/plain')
        response['Content-Disposition'] = f'attachment; filename="gamestate_integration_countertrak.cfg"'
        return response
    except SteamAccount.DoesNotExist:
        messages.error(request, 'Steam account not found or not linked to your account')
        return redirect('profile')
