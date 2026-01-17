from django.db import models
import uuid

class Match(models.Model):
    match_id = models.CharField(max_length=255, primary_key=True)
    game_mode = models.CharField(max_length=32)
    map_name = models.CharField(max_length=64)
    start_timestamp = models.DateTimeField()
    end_timestamp = models.DateTimeField(null=True, blank=True)
    rounds_played = models.IntegerField(default=0)
    team_ct_score = models.IntegerField(default=0)
    team_t_score = models.IntegerField(default=0)
    
    def __str__(self):
        return f"{self.map_name} ({self.match_id})"
    
    class Meta:
        verbose_name_plural = "Matches"

class Round(models.Model):
    match = models.ForeignKey(Match, on_delete=models.CASCADE, related_name='rounds')
    round_number = models.IntegerField()
    phase = models.CharField(max_length=32)
    timestamp = models.DateTimeField(auto_now_add=True)
    winning_team = models.CharField(max_length=32, null=True, blank=True)
    win_condition = models.CharField(max_length=64, null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['match', 'round_number'], name='unique_round')
        ]

    def __str__(self):
        return f"{self.match.map_name} - Round {self.round_number}"
