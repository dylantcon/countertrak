from django.contrib import admin
from .models import Weapon, PlayerRoundState, PlayerWeapon, PlayerMatchStat

class PlayerWeaponInline(admin.TabularInline):
    model = PlayerWeapon
    extra = 0
    readonly_fields = ('weapon', 'state', 'ammo_clip', 'ammo_reserve', 'paintkit')
    can_delete = False
    
    def has_add_permission(self, request, obj=None):
        return False

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
    
    inlines = [PlayerWeaponInline]
    
    def has_add_permission(self, request):
        return False

@admin.register(PlayerWeapon)
class PlayerWeaponAdmin(admin.ModelAdmin):
    list_display = ('get_match', 'get_round', 'get_player', 'weapon', 'state', 'ammo_clip', 'ammo_reserve')
    list_filter = ('state', 'weapon')
    search_fields = ('player_round_state__steam_account__player_name', 'weapon__name')
    readonly_fields = ('player_round_state', 'weapon')
    
    def get_match(self, obj):
        return obj.player_round_state.match
    get_match.short_description = 'Match'
    get_match.admin_order_field = 'player_round_state__match'
    
    def get_round(self, obj):
        return obj.player_round_state.round_number
    get_round.short_description = 'Round'
    get_round.admin_order_field = 'player_round_state__round_number'
    
    def get_player(self, obj):
        return obj.player_round_state.steam_account
    get_player.short_description = 'Player'
    get_player.admin_order_field = 'player_round_state__steam_account'
    
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
