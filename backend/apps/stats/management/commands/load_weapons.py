from django.core.management.base import BaseCommand
from apps.stats.models import Weapon

class Command(BaseCommand):
    help = 'Populates the Weapon table with CS2 weapons'

    def handle(self, *args, **options):
        weapons = [
            {'weapon_id': 1, 'name': 'weapon_knife', 'type': 'Knife', 'max_clip': None},
            {'weapon_id': 2, 'name': 'weapon_knife_t', 'type': 'Knife', 'max_clip': None},
            {'weapon_id': 3, 'name': 'weapon_glock', 'type': 'Pistol', 'max_clip': 20},
            {'weapon_id': 4, 'name': 'weapon_hkp2000', 'type': 'Pistol', 'max_clip': 13},
            {'weapon_id': 5, 'name': 'weapon_usp_silencer', 'type': 'Pistol', 'max_clip': 12},
        ]
        
        created_count = 0
        for weapon_data in weapons:
            _, created = Weapon.objects.update_or_create(
                weapon_id=weapon_data['weapon_id'],
                defaults={
                    'name': weapon_data['name'],
                    'type': weapon_data['type'],
                    'max_clip': weapon_data['max_clip']
                }
            )
            if created:
                created_count += 1
            
        self.stdout.write(self.style.SUCCESS(f'Successfully loaded {created_count} weapons'))
