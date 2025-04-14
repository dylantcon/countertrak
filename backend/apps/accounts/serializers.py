# apps/accounts/serializers.py
from rest_framework import serializers
from .models import SteamAccount

class SteamAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = SteamAccount
        fields = ['steam_id', 'player_name', 'auth_token']
        read_only_fields = ['auth_token']
