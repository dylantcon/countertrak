from django.db import models
from apps.accounts.models import SteamAccount
from apps.matches.models import Match, Round

class PlayerRoundState(models.Model):
    match = models.ForeignKey(Match, on_delete=models.CASCADE)
    round_number = models.IntegerField()
    steam_account = models.ForeignKey(SteamAccount, on_delete=models.CASCADE)
    health = models.IntegerField()
    armor = models.IntegerField()
    money = models.IntegerField()
    equip_value = models.IntegerField()
    round_kills = models.IntegerField(default=0)
    team = models.CharField(max_length=32, default='SPEC')
    state_timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['match', 'round_number', 'steam_account', 'state_timestamp'], 
                name='unique_player_round_state_temporal'
            )
        ]

class Weapon(models.Model):
    weapon_id = models.IntegerField(primary_key=True, unique=True)
    name = models.CharField(max_length=64, unique=True)
    type = models.CharField(max_length=32, null=True, blank=True)
    max_clip = models.IntegerField(null=True, blank=True)
    
    def __str__(self):
        return self.name

class PlayerWeapon(models.Model):
    # compound key components
    match = models.ForeignKey('matches.Match', null=True, blank=True, on_delete=models.CASCADE)
    round_number = models.IntegerField()
    steam_account = models.ForeignKey('accounts.SteamAccount', null=True, blank=True, on_delete=models.CASCADE)
    weapon = models.ForeignKey(Weapon, on_delete=models.PROTECT)

    # state fields
    state = models.CharField(max_length=32)
    ammo_clip = models.IntegerField(null=True, blank=True)
    ammo_reserve = models.IntegerField(null=True, blank=True)
    paintkit = models.CharField(max_length=64, default='default')
    state_timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['match', 'round_number', 'steam_account', 'weapon', 'state_timestamp'],
                name='unique_player_weapon_temporal'
            )
        ]

class PlayerMatchStat(models.Model):
    steam_account = models.ForeignKey(SteamAccount, on_delete=models.CASCADE)
    match = models.ForeignKey(Match, on_delete=models.CASCADE)
    kills = models.IntegerField(default=0)
    deaths = models.IntegerField(default=0)
    assists = models.IntegerField(default=0)
    mvps = models.IntegerField(default=0)
    score = models.IntegerField(default=0)
    
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['steam_account', 'match'], 
                name='unique_player_match_stat'
            )
        ]
