from django.core.management.base import BaseCommand
from apps.stats.models import Weapon
from apps.stats.weapon_data import WEAPONS, seed_weapons


class Command(BaseCommand):
    help = 'Populates the Weapon reference table with CS2 weapons'

    def handle(self, *args, **options):
        # The same seed runs automatically via data migration 0008_seed_weapons;
        # this command exists for manual re-seeding (e.g. after a bare `flush`,
        # which empties tables without re-running migrations). Both paths share
        # the canonical list in apps.stats.weapon_data, so they cannot drift.
        count = seed_weapons(Weapon)

        self.stdout.write(
            self.style.SUCCESS(
                f'The Weapon reference table is now populated with {count} '
                f'weapons (EXPECTED: {len(WEAPONS)})'
            )
        )
