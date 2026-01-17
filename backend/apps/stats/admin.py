from django.contrib import admin
from .models import Weapon, PlayerRoundState, PlayerWeapon, PlayerMatchStat

@admin.register(Weapon)
class WeaponAdmin(admin.ModelAdmin):
    list_display = ('weapon_id', 'name', 'type', 'max_clip')
    list_filter = ('type',)
    search_fields = ('name', 'type')

@admin.register(PlayerRoundState)
class PlayerRoundStateAdmin(admin.ModelAdmin):
    list_display = ('match', 'round_number', 'steam_account', 'health', 'armor', 'money', 'round_kills')
    list_filter = ('match', 'round_number')
    search_fields = ('match__match_id', 'steam_account__player_name')
    readonly_fields = ('match', 'round_number', 'steam_account')
    
    def has_add_permission(self, request):
        return False

@admin.register(PlayerWeapon)
class PlayerWeaponAdmin(admin.ModelAdmin):
    list_display = ('match', 'round_number', 'steam_account', 'weapon', 'state', 'ammo_clip', 'ammo_reserve')
    list_filter = ('state', 'weapon', 'match')
    search_fields = ('steam_account__player_name', 'weapon__name', 'match__match_id')
    readonly_fields = ('match', 'round_number', 'steam_account', 'weapon')

    def has_add_permission(self, request):
        return False

@admin.register(PlayerMatchStat)
class PlayerMatchStatAdmin(admin.ModelAdmin):
    list_display = ('steam_account', 'match', 'kills', 'deaths', 'assists', 'mvps', 'score')
    list_filter = ('match',)
    search_fields = ('steam_account__player_name', 'match__match_id')
    readonly_fields = ('steam_account', 'match')
    
    def has_add_permission(self, request):
        return False
