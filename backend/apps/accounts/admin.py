from django.contrib import admin
from .models import SteamAccount

@admin.register(SteamAccount)
class SteamAccountAdmin(admin.ModelAdmin):
    list_display = ('steam_id', 'player_name', 'user', 'auth_token')
    search_fields = ('steam_id', 'player_name', 'user__username')
    list_filter = ('user',)
    readonly_fields = ('auth_token',)
    
    fieldsets = (
        (None, {
            'fields': ('steam_id', 'player_name', 'user')
        }),
        ('Authentication', {
            'fields': ('auth_token',),
            'classes': ('collapse',),
            'description': 'Authentication token for GSI integration'
        }),
    )
    
    def get_readonly_fields(self, request, obj=None):
        # Make steam_id readonly if editing an existing object
        if obj:
            return self.readonly_fields + ('steam_id',)
        return self.readonly_fields
