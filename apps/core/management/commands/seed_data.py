"""
KLA WasteNet Pro — Seed Data Command
Creates initial categories, demo users, and sample data for development
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import transaction

User = get_user_model()


WASTE_CATEGORIES = [
    {
        'name': 'General Household Waste',
        'slug': 'general-household',
        'icon': '🗑️',
        'color': '#6B7280',
        'base_fee': 15000,
        'is_hazardous': False,
        'is_recyclable': False,
        'sort_order': 1,
        'description': 'Everyday household rubbish including food scraps, packaging, etc.',
    },
    {
        'name': 'Organic / Food Waste',
        'slug': 'organic-food',
        'icon': '🍃',
        'color': '#16A34A',
        'base_fee': 12000,
        'is_hazardous': False,
        'is_recyclable': True,
        'sort_order': 2,
        'description': 'Food scraps, garden waste, and compostable materials.',
    },
    {
        'name': 'Plastic & Packaging',
        'slug': 'plastic-packaging',
        'icon': '♻️',
        'color': '#2563EB',
        'base_fee': 10000,
        'is_hazardous': False,
        'is_recyclable': True,
        'sort_order': 3,
        'description': 'Plastic bottles, bags, containers, and packaging materials.',
    },
    {
        'name': 'Electronics (E-Waste)',
        'slug': 'e-waste',
        'icon': '💻',
        'color': '#7C3AED',
        'base_fee': 25000,
        'is_hazardous': True,
        'is_recyclable': True,
        'sort_order': 4,
        'description': 'Old phones, computers, TVs, and electronic accessories.',
    },
    {
        'name': 'Construction Debris',
        'slug': 'construction-debris',
        'icon': '🏗️',
        'color': '#D97706',
        'base_fee': 45000,
        'is_hazardous': False,
        'is_recyclable': False,
        'sort_order': 5,
        'description': 'Rubble, sand, cement, broken tiles, and building waste.',
    },
    {
        'name': 'Medical / Hazardous Waste',
        'slug': 'medical-hazardous',
        'icon': '☣️',
        'color': '#DC2626',
        'base_fee': 60000,
        'is_hazardous': True,
        'is_recyclable': False,
        'sort_order': 6,
        'description': 'Medical waste, chemicals, batteries, and hazardous materials. Requires special handling.',
    },
    {
        'name': 'Bulky Items',
        'slug': 'bulky-items',
        'icon': '🛋️',
        'color': '#0891B2',
        'base_fee': 35000,
        'is_hazardous': False,
        'is_recyclable': False,
        'sort_order': 7,
        'description': 'Furniture, mattresses, large appliances, and oversized items.',
    },
    {
        'name': 'Garden & Green Waste',
        'slug': 'garden-green',
        'icon': '🌿',
        'color': '#059669',
        'base_fee': 12000,
        'is_hazardous': False,
        'is_recyclable': True,
        'sort_order': 8,
        'description': 'Grass clippings, tree branches, leaves, and garden trimmings.',
    },
]

DEMO_USERS = [
    {
        'username': 'superadmin',
        'password': 'KLAAdmin@2024!',
        'email': 'admin@klawastenet.go.ug',
        'first_name': 'KCCA',
        'last_name': 'Administrator',
        'role': 'super_admin',
        'is_staff': True,
        'is_superuser': True,
        'is_verified': True,
    },
    {
        'username': 'kcca_official',
        'password': 'KLAOfficial@2024!',
        'email': 'official@klawastenet.go.ug',
        'first_name': 'Jennifer',
        'last_name': 'Nakato',
        'role': 'kcca_official',
        'division': 'central',
        'is_verified': True,
    },
    {
        'username': 'admin_kawempe',
        'password': 'KLAAdmin@2024!',
        'email': 'kawempe@klawastenet.go.ug',
        'first_name': 'Patrick',
        'last_name': 'Ssemakula',
        'role': 'admin',
        'division': 'kawempe',
        'is_verified': True,
    },
    {
        'username': 'collector_01',
        'password': 'KLACollect@2024!',
        'email': 'collector1@klawastenet.go.ug',
        'first_name': 'Moses',
        'last_name': 'Ochieng',
        'role': 'collector',
        'division': 'kawempe',
        'phone': '+256701000001',
        'is_verified': True,
    },
    {
        'username': 'collector_02',
        'password': 'KLACollect@2024!',
        'email': 'collector2@klawastenet.go.ug',
        'first_name': 'Sarah',
        'last_name': 'Atim',
        'role': 'collector',
        'division': 'makindye',
        'phone': '+256701000002',
        'is_verified': True,
    },
    {
        'username': 'resident_01',
        'password': 'KLAResident@2024!',
        'email': 'resident1@gmail.com',
        'first_name': 'Grace',
        'last_name': 'Namukasa',
        'role': 'resident',
        'division': 'kawempe',
        'phone': '+256702000001',
        'address': 'Plot 45, Bombo Road, Kawempe',
        'is_verified': True,
    },
    {
        'username': 'resident_02',
        'password': 'KLAResident@2024!',
        'email': 'resident2@gmail.com',
        'first_name': 'David',
        'last_name': 'Mutebi',
        'role': 'resident',
        'division': 'nakawa',
        'phone': '+256702000002',
        'address': 'Plot 12, Jinja Road, Nakawa',
        'is_verified': True,
    },
]


class Command(BaseCommand):
    help = 'Seed KLA WasteNet with initial data (categories, demo users, sample requests)'

    def add_arguments(self, parser):
        parser.add_argument('--categories', action='store_true', help='Seed waste categories')
        parser.add_argument('--superuser', action='store_true', help='Create demo superuser')
        parser.add_argument('--demo-users', action='store_true', help='Create all demo users')
        parser.add_argument('--smart-bins', action='store_true', help='Create sample smart bins')
        parser.add_argument('--all', action='store_true', help='Seed everything')

    def handle(self, *args, **options):
        seed_all = options.get('all')

        if seed_all or options.get('categories'):
            self._seed_categories()

        if seed_all or options.get('superuser') or options.get('demo_users'):
            self._seed_users(options)

        if seed_all or options.get('smart_bins'):
            self._seed_smart_bins()

        self.stdout.write(self.style.SUCCESS('\n✅ KLA WasteNet seeding complete!'))

    @transaction.atomic
    def _seed_categories(self):
        from apps.waste.models import WasteCategory
        created = 0
        for cat_data in WASTE_CATEGORIES:
            _, was_created = WasteCategory.objects.get_or_create(
                slug=cat_data['slug'],
                defaults=cat_data,
            )
            if was_created:
                created += 1

        self.stdout.write(self.style.SUCCESS(f'  📦 Waste categories: {created} created ({len(WASTE_CATEGORIES)} total)'))

    @transaction.atomic
    def _seed_users(self, options):
        from apps.accounts.models import CollectorProfile

        seed_all_users = options.get('all') or options.get('demo_users')
        user_list = DEMO_USERS if seed_all_users else [DEMO_USERS[0]]  # Just superadmin

        created = 0
        for u in user_list:
            password = u.pop('password')
            is_superuser = u.pop('is_superuser', False)
            is_staff = u.pop('is_staff', False)

            user, was_created = User.objects.get_or_create(
                username=u['username'],
                defaults={**u}
            )

            if was_created:
                user.set_password(password)
                user.is_superuser = is_superuser
                user.is_staff = is_staff
                user.save()

                # Create collector profile
                if user.role == 'collector':
                    count = User.objects.filter(role='collector').count()
                    CollectorProfile.objects.get_or_create(
                        user=user,
                        defaults={
                            'employee_id': f'KLA{count:04d}',
                            'vehicle_type': 'truck',
                            'capacity_kg': 1000,
                        }
                    )

                created += 1

            u['password'] = password  # restore for next iteration

        self.stdout.write(self.style.SUCCESS(f'  👥 Demo users: {created} created'))
        self.stdout.write('     Login credentials:')
        for u in (DEMO_USERS if seed_all_users else [DEMO_USERS[0]]):
            self.stdout.write(f'       {u["username"]:20s} / {u["password"]}  [{u["role"]}]')

    @transaction.atomic
    def _seed_smart_bins(self):
        from apps.waste.models import SmartBin, WasteCategory

        general_cat = WasteCategory.objects.filter(slug='general-household').first()

        bins = [
            {'bin_id': 'KLA-BIN-001', 'location_name': 'Owino Market Main Entrance', 'division': 'central', 'latitude': 0.3168, 'longitude': 32.5754, 'fill_level': 85},
            {'bin_id': 'KLA-BIN-002', 'location_name': 'Nakivubo Bus Terminal', 'division': 'central', 'latitude': 0.3175, 'longitude': 32.5800, 'fill_level': 60},
            {'bin_id': 'KLA-BIN-003', 'location_name': 'Kawempe Roundabout', 'division': 'kawempe', 'latitude': 0.3752, 'longitude': 32.5548, 'fill_level': 45},
            {'bin_id': 'KLA-BIN-004', 'location_name': 'Makindye Market', 'division': 'makindye', 'latitude': 0.2956, 'longitude': 32.5821, 'fill_level': 90},
            {'bin_id': 'KLA-BIN-005', 'location_name': 'Nakawa Industrial Area', 'division': 'nakawa', 'latitude': 0.3318, 'longitude': 32.6213, 'fill_level': 30},
            {'bin_id': 'KLA-BIN-006', 'location_name': 'Rubaga Hospital Gate', 'division': 'rubaga', 'latitude': 0.3198, 'longitude': 32.5501, 'fill_level': 70},
        ]

        created = 0
        for b in bins:
            _, was_created = SmartBin.objects.get_or_create(
                bin_id=b['bin_id'],
                defaults={**b, 'waste_category': general_cat, 'capacity_liters': 240}
            )
            if was_created:
                created += 1

        self.stdout.write(self.style.SUCCESS(f'  🗑️  Smart bins: {created} created ({len(bins)} total)'))
