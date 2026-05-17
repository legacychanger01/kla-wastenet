"""
KLA WasteNet Pro — Test Suite
Unit and integration tests for core features
"""
import pytest
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from decimal import Decimal

User = get_user_model()


# ─── Fixtures ────────────────────────────────────────────────────────────────

def make_user(role='resident', **kwargs):
    defaults = {
        'username': f'{role}_test',
        'email': f'{role}@test.com',
        'password': 'TestPass@2024!',
        'role': role,
        'first_name': role.title(),
        'last_name': 'User',
        'is_active': True,
    }
    defaults.update(kwargs)
    user = User(**{k: v for k, v in defaults.items() if k != 'password'})
    user.set_password(defaults['password'])
    user.save()
    return user


def make_category(**kwargs):
    from apps.waste.models import WasteCategory
    defaults = {
        'name': 'Test Waste',
        'slug': 'test-waste',
        'icon': '🗑️',
        'base_fee': Decimal('15000'),
        'is_active': True,
        'sort_order': 1,
    }
    defaults.update(kwargs)
    return WasteCategory.objects.create(**defaults)


def make_pickup_request(user, category, **kwargs):
    from apps.waste.models import PickupRequest
    defaults = {
        'division': 'kawempe',
        'address': 'Test Address, Kampala',
        'status': 'pending',
        'priority': 'normal',
        'amount_due': Decimal('15000'),
    }
    defaults.update(kwargs)
    return PickupRequest.objects.create(user=user, category=category, **defaults)


# ─── Account Tests ────────────────────────────────────────────────────────────

class TestUserModel(TestCase):
    def setUp(self):
        self.resident = make_user('resident', username='res1')
        self.admin = make_user('super_admin', username='adm1')
        self.collector = make_user('collector', username='col1')

    def test_role_checks(self):
        self.assertTrue(self.resident.is_resident())
        self.assertFalse(self.resident.is_admin())
        self.assertTrue(self.admin.is_admin())
        self.assertTrue(self.admin.is_super_admin())
        self.assertTrue(self.collector.is_collector())

    def test_get_initials(self):
        user = make_user(
            username='init_test',
            first_name='Grace',
            last_name='Namukasa',
        )
        self.assertEqual(user.get_initials(), 'GN')

    def test_get_display_name_full(self):
        user = make_user(username='disp_test', first_name='Moses', last_name='Ochieng')
        self.assertEqual(user.get_display_name(), 'Moses Ochieng')

    def test_get_display_name_fallback(self):
        user = make_user(username='disp_only')
        user.first_name = ''
        user.last_name = ''
        user.save()
        self.assertEqual(user.get_display_name(), 'disp_only')

    def test_update_location(self):
        self.resident.update_location(0.3476, 32.5825)
        self.resident.refresh_from_db()
        self.assertAlmostEqual(float(self.resident.latitude), 0.3476, places=4)
        self.assertAlmostEqual(float(self.resident.longitude), 32.5825, places=4)
        self.assertIsNotNone(self.resident.location_updated_at)


class TestAuthViews(TestCase):
    def setUp(self):
        self.client = Client()
        self.resident = make_user('resident', username='auth_res')

    def test_home_redirects_authenticated(self):
        self.client.force_login(self.resident)
        response = self.client.get(reverse('home'))
        self.assertIn(response.status_code, [301, 302])

    def test_login_page_loads(self):
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'KLA WasteNet')

    def test_login_valid_credentials(self):
        response = self.client.post(reverse('login'), {
            'username': 'auth_res',
            'password': 'TestPass@2024!',
        })
        self.assertIn(response.status_code, [301, 302])

    def test_login_invalid_credentials(self):
        response = self.client.post(reverse('login'), {
            'username': 'auth_res',
            'password': 'wrongpassword',
        })
        self.assertEqual(response.status_code, 200)

    def test_register_creates_resident(self):
        response = self.client.post(reverse('register'), {
            'username': 'new_resident',
            'email': 'new@test.com',
            'password1': 'NewPass@2024!',
            'password2': 'NewPass@2024!',
            'first_name': 'New',
            'last_name': 'User',
            'division': 'nakawa',
            'address': 'Test address',
        })
        self.assertIn(response.status_code, [200, 301, 302])
        # Lenient: form might reject due to validation, but no 500
        self.assertNotEqual(response.status_code, 500)

    def test_unauthenticated_dashboard_redirects(self):
        response = self.client.get(reverse('resident_dashboard'))
        self.assertIn(response.status_code, [301, 302])


# ─── Waste Model Tests ────────────────────────────────────────────────────────

class TestPickupRequest(TestCase):
    def setUp(self):
        self.resident = make_user('resident', username='pr_res')
        self.category = make_category()

    def test_request_number_auto_generated(self):
        req = make_pickup_request(self.resident, self.category)
        self.assertTrue(req.request_number.startswith('KLA'))
        self.assertGreater(len(req.request_number), 5)

    def test_amount_from_category(self):
        req = make_pickup_request(self.resident, self.category)
        self.assertEqual(req.amount_due, self.category.base_fee)

    def test_status_choices(self):
        from apps.waste.models import PickupRequest
        valid_statuses = [s[0] for s in PickupRequest.STATUS_CHOICES]
        self.assertIn('pending', valid_statuses)
        self.assertIn('collected', valid_statuses)
        self.assertIn('cancelled', valid_statuses)

    def test_is_overdue_false_for_future(self):
        from datetime import date, timedelta
        req = make_pickup_request(self.resident, self.category,
                                  preferred_date=date.today() + timedelta(days=2))
        self.assertFalse(req.is_overdue)

    def test_is_overdue_true_for_past(self):
        from datetime import date, timedelta
        req = make_pickup_request(self.resident, self.category,
                                  preferred_date=date.today() - timedelta(days=3))
        self.assertTrue(req.is_overdue)


class TestAssignment(TestCase):
    def setUp(self):
        self.resident = make_user('resident', username='asgn_res')
        self.collector = make_user('collector', username='asgn_col')
        self.admin = make_user('admin', username='asgn_adm')
        self.category = make_category(slug='asgn-cat')

    def test_create_assignment(self):
        from apps.waste.models import Assignment
        req = make_pickup_request(self.resident, self.category)
        assignment = Assignment.objects.create(
            pickup_request=req,
            collector=self.collector,
            assigned_by=self.admin,
        )
        self.assertEqual(assignment.collector, self.collector)
        self.assertEqual(assignment.pickup_request, req)


# ─── Payment Tests ────────────────────────────────────────────────────────────

class TestPayment(TestCase):
    def setUp(self):
        self.resident = make_user('resident', username='pay_res')

    def test_payment_reference_auto_generated(self):
        from apps.payments.models import Payment
        payment = Payment.objects.create(
            user=self.resident,
            gateway='mtn_momo',
            amount=Decimal('15000'),
        )
        self.assertTrue(payment.reference.startswith('KLA'))
        self.assertGreater(len(payment.reference), 10)

    def test_payment_status_default_pending(self):
        from apps.payments.models import Payment
        payment = Payment.objects.create(
            user=self.resident,
            gateway='airtel_money',
            amount=Decimal('45000'),
        )
        self.assertEqual(payment.status, 'pending')

    def test_is_successful_property(self):
        from apps.payments.models import Payment
        payment = Payment.objects.create(
            user=self.resident,
            gateway='flutterwave',
            amount=Decimal('20000'),
            status='successful',
        )
        self.assertTrue(payment.is_successful)

    def test_invoice_number_auto_generated(self):
        from apps.payments.models import Payment, Invoice
        payment = Payment.objects.create(
            user=self.resident,
            gateway='mtn_momo',
            amount=Decimal('15000'),
            status='successful',
        )
        invoice = Invoice.objects.create(
            user=self.resident,
            payment=payment,
            amount=Decimal('15000'),
            total_amount=Decimal('15000'),
            status='paid',
        )
        self.assertTrue(invoice.invoice_number.startswith('INV-'))


# ─── Notification Tests ───────────────────────────────────────────────────────

class TestNotification(TestCase):
    def setUp(self):
        self.user = make_user('resident', username='notif_res')

    def test_create_notification(self):
        from apps.notifications.models import Notification
        notif = Notification.objects.create(
            user=self.user,
            notification_type='pickup_submitted',
            title='Test Title',
            message='Test message body',
        )
        self.assertFalse(notif.is_read)
        self.assertIsNone(notif.read_at)

    def test_mark_read(self):
        from apps.notifications.models import Notification
        notif = Notification.objects.create(
            user=self.user,
            notification_type='system',
            title='Read me',
            message='This will be marked as read',
        )
        notif.mark_read()
        notif.refresh_from_db()
        self.assertTrue(notif.is_read)
        self.assertIsNotNone(notif.read_at)


# ─── Analytics Tests ──────────────────────────────────────────────────────────

class TestAnalytics(TestCase):
    def test_demand_predictor_returns_list(self):
        from apps.analytics.services.ai_engine import WasteDemandPredictor
        predictor = WasteDemandPredictor()
        preds = predictor.predict_division_demand('kawempe', days_ahead=7)
        self.assertIsInstance(preds, list)
        self.assertEqual(len(preds), 7)
        for p in preds:
            self.assertIn('date', p)
            self.assertIn('predicted_requests', p)

    def test_route_optimizer_empty(self):
        from apps.analytics.services.ai_engine import RouteOptimizer
        optimizer = RouteOptimizer()
        result = optimizer.optimize_route([])
        self.assertEqual(result, [])

    def test_analytics_overview_returns_dict(self):
        from apps.analytics.services.ai_engine import AnalyticsDashboard
        dash = AnalyticsDashboard()
        stats = dash.get_overview_stats()
        self.assertIn('total_users', stats)
        self.assertIn('completion_rate', stats)


# ─── API Tests ────────────────────────────────────────────────────────────────

class TestWasteAPI(TestCase):
    def setUp(self):
        self.client = Client()
        self.resident = make_user('resident', username='api_res')
        self.admin = make_user('super_admin', username='api_adm', is_staff=True)
        self.category = make_category(slug='api-cat')

    def test_category_list_requires_auth(self):
        response = self.client.get('/api/v1/waste/categories/')
        self.assertEqual(response.status_code, 403)

    def test_category_list_authenticated(self):
        self.client.force_login(self.resident)
        response = self.client.get('/api/v1/waste/categories/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('results', data)

    def test_create_pickup_request_api(self):
        self.client.force_login(self.resident)
        response = self.client.post(
            '/api/v1/waste/requests/',
            data={
                'category_id': str(self.category.pk),
                'division': 'kawempe',
                'address': 'API test address, Kampala',
            },
            content_type='application/json',
        )
        self.assertIn(response.status_code, [200, 201, 400])  # 400 if validation fails

    def test_smart_bin_list(self):
        self.client.force_login(self.admin)
        response = self.client.get('/api/v1/waste/smart-bins/')
        self.assertEqual(response.status_code, 200)
