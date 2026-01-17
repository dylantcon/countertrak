# apps/stats/serializers.py
from rest_framework import serializers
from .models import PlayerMatchStat, PlayerRoundState, PlayerWeapon, Weapon

class WeaponSerializer(serializers.ModelSerializer):
    class Meta:
        model = Weapon
        fields = ['weapon_id', 'name', 'type', 'max_clip']

class PlayerMatchStatSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlayerMatchStat
        fields = ['steam_account', 'match', 'kills', 'deaths', 'assists', 'mvps', 'score']
