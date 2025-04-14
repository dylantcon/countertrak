from django.db import models

class SteamAccount(models.Model):
    steam_id = models.CharField(max_length=64, primary_key=True)
    user = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='steam_accounts')
    auth_token = models.CharField(max_length=128, unique=True)
    player_name = models.CharField(max_length=100)

    def generate_auth_token(self):
        """ generate unique auth token using steam_id and a random component """
        import uuid
        import hashlib
        random_component = uuid.uuid4().hex
        token_base = f"{self.steam_id}:{random_component}"
        return hashlib.sha256(token_base.encode()).hexdigest()[:32].upper()

    def save(self, *args, **kwargs):
        if not self.auth_token:
            self.auth_token = self.generate_auth_token()
        super().save(*args, **kwargs)
        
    def __str__(self):
        return f"{self.player_name} ({self.steam_id})"
