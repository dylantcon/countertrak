# Step 1: Add new fields
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0002_alter_steamaccount_user'),
        ('matches', '0001_initial'),
        ('stats', '0003_alter_weapon_type_alter_weapon_weapon_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='playerweapon',
            name='match',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='matches.match'),
        ),
        migrations.AddField(
            model_name='playerweapon',
            name='round_number',
            field=models.IntegerField(default=0),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='playerweapon',
            name='steam_account',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='accounts.steamaccount'),
        ),
        # Remove the old constraint
        migrations.RemoveConstraint(
            model_name='playerweapon',
            name='unique_player_weapon_temporal',
        ),
    ]
