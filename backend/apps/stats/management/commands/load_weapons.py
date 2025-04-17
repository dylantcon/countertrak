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
            {'weapon_id': 6, 'name': 'weapon_elite', 'type': 'Pistol', 'max_clip': 30},
            {'weapon_id': 7, 'name': 'weapon_p250', 'type': 'Pistol', 'max_clip': 13},
            {'weapon_id': 8, 'name': 'weapon_tec9', 'type': 'Pistol', 'max_clip': 18},
            {'weapon_id': 9, 'name': 'weapon_fiveseven', 'type': 'Pistol', 'max_clip': 20},
            {'weapon_id': 10, 'name': 'weapon_deagle', 'type': 'Pistol', 'max_clip': 7},
            {'weapon_id': 11, 'name': 'weapon_revolver', 'type': 'Pistol', 'max_clip': 8},
            {'weapon_id': 12, 'name': 'weapon_cz75a', 'type': 'Pistol', 'max_clip': 12},
            {'weapon_id': 13, 'name': 'weapon_mag7', 'type': 'Shotgun', 'max_clip': 5},
            {'weapon_id': 14, 'name': 'weapon_sawedoff', 'type': 'Shotgun', 'max_clip': 7},
            {'weapon_id': 15, 'name': 'weapon_nova', 'type': 'Shotgun', 'max_clip': 8},
            {'weapon_id': 16, 'name': 'weapon_xm1014', 'type': 'Shotgun', 'max_clip': 7},
            {'weapon_id': 17, 'name': 'weapon_mp9', 'type': 'Submachine Gun', 'max_clip': 30},
            {'weapon_id': 18, 'name': 'weapon_mac10', 'type': 'Submachine Gun', 'max_clip': 30},
            {'weapon_id': 19, 'name': 'weapon_bizon', 'type': 'Submachine Gun', 'max_clip': 64},
            {'weapon_id': 20, 'name': 'weapon_mp7', 'type': 'Submachine Gun', 'max_clip': 30},
            {'weapon_id': 21, 'name': 'weapon_ump45', 'type': 'Submachine Gun', 'max_clip': 25},
            {'weapon_id': 22, 'name': 'weapon_p90', 'type': 'Submachine Gun', 'max_clip': 50},
            {'weapon_id': 23, 'name': 'weapon_mp5sd', 'type': 'Submachine Gun', 'max_clip': 30},
            {'weapon_id': 24, 'name': 'weapon_famas', 'type': 'Rifle', 'max_clip': 25},
            {'weapon_id': 25, 'name': 'weapon_galilar', 'type': 'Rifle', 'max_clip': 35},
            {'weapon_id': 26, 'name': 'weapon_m4a1', 'type': 'Rifle', 'max_clip': 30},
            {'weapon_id': 27, 'name': 'weapon_m4a1_silencer', 'type': 'Rifle', 'max_clip': 20},
            {'weapon_id': 28, 'name': 'weapon_ak47', 'type': 'Rifle', 'max_clip': 30},
            {'weapon_id': 29, 'name': 'weapon_aug', 'type': 'Rifle', 'max_clip': 30},
            {'weapon_id': 30, 'name': 'weapon_sg556', 'type': 'Rifle', 'max_clip': 30},
            {'weapon_id': 31, 'name': 'weapon_ssg08', 'type': 'SniperRifle', 'max_clip': 10},
            {'weapon_id': 32, 'name': 'weapon_awp', 'type': 'SniperRifle', 'max_clip': 5},
            {'weapon_id': 33, 'name': 'weapon_scar20', 'type': 'SniperRifle', 'max_clip': 20},
            {'weapon_id': 34, 'name': 'weapon_g3sg1', 'type': 'SniperRifle', 'max_clip': 20},
            {'weapon_id': 35, 'name': 'weapon_m249', 'type': 'Machine Gun', 'max_clip': 100},
            {'weapon_id': 36, 'name': 'weapon_negev', 'type': 'Machine Gun', 'max_clip': 150},
            {'weapon_id': 37, 'name': 'weapon_decoy', 'type': 'Grenade', 'max_clip': None },
            {'weapon_id': 38, 'name': 'weapon_flashbang', 'type': 'Grenade', 'max_clip': None },
            {'weapon_id': 39, 'name': 'weapon_smokegrenade', 'type': 'Grenade', 'max_clip': None },
            {'weapon_id': 40, 'name': 'weapon_hegrenade', 'type': 'Grenade', 'max_clip': None },
            {'weapon_id': 41, 'name': 'weapon_incgrenade', 'type': 'Grenade', 'max_clip': None },
            {'weapon_id': 42, 'name': 'weapon_molotov', 'type': 'Grenade', 'max_clip': None },
            {'weapon_id': 43, 'name': 'weapon_c4', 'type': 'C4', 'max_clip': None },
            {'weapon_id': 44, 'name': 'weapon_healthshot', 'type': 'StackableItem', 'max_clip': None },
            {'weapon_id': 45, 'name': 'weapon_taser', 'type': None, 'max_clip': 1 },
        ]

        for weapon_data in weapons:
            obj, created = Weapon.objects.update_or_create(
                weapon_id=weapon_data['weapon_id'],
                defaults={
                    'name': weapon_data['name'],
                    'type': weapon_data['type'],
                    'max_clip': weapon_data['max_clip']
                }
            )

        self.stdout.write(
            self.style.SUCCESS(
                f'The Weapon reference table is now populated with {Weapon.objects.count()} weapons (EXPECTED: 45)'
            )
        )
