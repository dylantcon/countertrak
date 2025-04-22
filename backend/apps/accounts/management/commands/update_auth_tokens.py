from django.core.management.base import BaseCommand
from apps.accounts.models import SteamAccount

class Command(BaseCommand):
    help = 'Updates auth tokens for all Steam accounts'

    def handle(self, *args, **options):
        count = 0
        for account in SteamAccount.objects.all():
            old_token = account.auth_token
            account.auth_token = account.generate_auth_token()
            account.save()
            count += 1
            self.stdout.write(f"Updated token for {account.player_name}: {old_token} → {account.auth_token}")
        
        self.stdout.write(self.style.SUCCESS(f"Updated auth tokens for {count} accounts"))
