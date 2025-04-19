# Step 3: Remove old field and add constraint
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('stats', '0005_data_migration'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='playerweapon',
            name='player_round_state',
        ),
        # Add the new compound key constraint
        migrations.AddConstraint(
            model_name='playerweapon',
            constraint=models.UniqueConstraint(
                fields=['match', 'round_number', 'steam_account', 'weapon', 'state_timestamp'],
                name='unique_player_weapon_temporal'
            ),
        ),
    ]
