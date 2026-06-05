from django.db import migrations

from apps.stats.weapon_data import seed_weapons


def forwards(apps, schema_editor):
    # Use the historical model so this migration is stable regardless of later
    # changes to the live Weapon model. seed_weapons() is an idempotent upsert,
    # so applying this on an already-seeded database is a harmless no-op.
    Weapon = apps.get_model('stats', 'Weapon')
    seed_weapons(Weapon)


class Migration(migrations.Migration):

    dependencies = [
        ('stats', '0007_playerroundstate_team_alter_playerweapon_match_and_more'),
    ]

    operations = [
        # Reverse is a no-op: we never want unapplying a later migration to wipe
        # the reference table out from under existing PlayerWeapon foreign keys.
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
