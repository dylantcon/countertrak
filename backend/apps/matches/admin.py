from django.contrib import admin
from .models import Match, Round

class RoundInline(admin.TabularInline):
    model = Round
    extra = 0
    readonly_fields = ('round_number', 'phase', 'timestamp', 'winning_team', 'win_condition')
    can_delete = False
    
    def has_add_permission(self, request, obj=None):
        return False

@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = ('match_id', 'map_name', 'game_mode', 'start_timestamp', 'team_ct_score', 'team_t_score', 'rounds_played')
    list_filter = ('map_name', 'game_mode')
    search_fields = ('match_id', 'map_name')
    readonly_fields = ('match_id', 'start_timestamp')
    
    fieldsets = (
        (None, {
            'fields': ('match_id', 'map_name', 'game_mode')
        }),
        ('Match Details', {
            'fields': ('start_timestamp', 'end_timestamp', 'rounds_played')
        }),
        ('Score', {
            'fields': ('team_ct_score', 'team_t_score')
        }),
    )
    
    inlines = [RoundInline]
    
    def has_add_permission(self, request):
        # Matches are created by the GSI system, not manually
        return False

@admin.register(Round)
class RoundAdmin(admin.ModelAdmin):
    list_display = ('match', 'round_number', 'phase', 'winning_team', 'win_condition')
    list_filter = ('match', 'winning_team', 'phase')
    search_fields = ('match__match_id', 'winning_team')
    readonly_fields = ('match', 'round_number', 'timestamp')
    
    def has_add_permission(self, request):
        # Rounds are created by the GSI system, not manually
        return False
