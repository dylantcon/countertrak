# Step 2: Data migration
from django.db import migrations

def forward_data(apps, schema_editor):
    PlayerWeapon = apps.get_model('stats', 'PlayerWeapon')
    for pw in PlayerWeapon.objects.all():
        # Get related data from player_round_state
        prs = pw.player_round_state
        pw.match_id = prs.match_id
        pw.round_number = prs.round_number
        pw.steam_account_id = prs.steam_account_id
        pw.save()

class Migration(migrations.Migration):
    dependencies = [
        ('stats', '0004_add_new_fields'),
    ]

    operations = [
        migrations.RunPython(forward_data),
    ]
