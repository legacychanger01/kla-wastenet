"""
KLA WasteNet Pro — Accounts Models
Extended user model with full profile, 2FA, subscription management
"""
import uuid
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from django.core.validators import RegexValidator


phone_validator = RegexValidator(
    regex=r'^\+?256?\d{9}$',
    message='Enter a valid Ugandan phone number (e.g., +256700000000)'
)


class User(AbstractUser):
    ROLE_CHOICES = [
        ('super_admin', 'Super Administrator'),
        ('kcca_official', 'KCCA Official'),
        ('admin', 'Division Admin'),
        ('resident', 'Resident'),
        ('collector', 'Waste Collector'),
        ('recycler', 'Recycling Company'),
    ]

    DIVISION_CHOICES = [
        ('central', 'Central Division'),
        ('kawempe', 'Kawempe Division'),
        ('makindye', 'Makindye Division'),
        ('nakawa', 'Nakawa Division'),
        ('rubaga', 'Rubaga Division'),
    ]

    LANGUAGE_CHOICES = [
        ('en', 'English'),
        ('lg', 'Luganda'),
        ('sw', 'Kiswahili'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='resident', db_index=True)
    phone = models.CharField(max_length=20, validators=[phone_validator], blank=True)
    division = models.CharField(max_length=50, choices=DIVISION_CHOICES, blank=True, db_index=True)
    address = models.TextField(blank=True)
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    bio = models.TextField(blank=True, max_length=500)
    language = models.CharField(max_length=5, choices=LANGUAGE_CHOICES, default='en')

    # Location
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    location_updated_at = models.DateTimeField(null=True, blank=True)

    # Verification & Security
    is_verified = models.BooleanField(default=False)
    is_phone_verified = models.BooleanField(default=False)
    two_factor_enabled = models.BooleanField(default=False)
    email_verified_at = models.DateTimeField(null=True, blank=True)
    failed_login_count = models.PositiveIntegerField(default=0)
    last_login_ip = models.GenericIPAddressField(null=True, blank=True)

    # Preferences
    email_notifications = models.BooleanField(default=True)
    sms_notifications = models.BooleanField(default=True)
    push_notifications = models.BooleanField(default=True)
    fcm_token = models.TextField(blank=True)  # Firebase push token
    dark_mode = models.BooleanField(default=False)

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_active = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)  # Admin notes

    class Meta:
        db_table = 'accounts_user'
        indexes = [
            models.Index(fields=['role', 'division']),
            models.Index(fields=['is_active', 'role']),
            models.Index(fields=['email']),
        ]

    def is_super_admin(self): return self.role == 'super_admin'
    def is_kcca_official(self): return self.role == 'kcca_official'
    def is_admin(self): return self.role in ('admin', 'super_admin', 'kcca_official')
    def is_resident(self): return self.role == 'resident'
    def is_collector(self): return self.role == 'collector'
    def is_recycler(self): return self.role == 'recycler'

    def get_display_name(self):
        return self.get_full_name() or self.username

    def get_initials(self):
        fn = (self.first_name or '').strip()
        ln = (self.last_name or '').strip()
        if fn and ln:
            return f"{fn[0]}{ln[0]}".upper()
        return (self.username[:2]).upper()

    def update_location(self, lat, lng):
        self.latitude = lat
        self.longitude = lng
        self.location_updated_at = timezone.now()
        self.save(update_fields=['latitude', 'longitude', 'location_updated_at'])

    def __str__(self):
        return f"{self.get_display_name()} ({self.get_role_display()})"


class CollectorProfile(models.Model):
    """Extended profile for waste collectors"""
    VEHICLE_CHOICES = [
        ('truck', 'Waste Truck'),
        ('pickup', 'Pickup Van'),
        ('motorcycle', 'Motorcycle'),
        ('handcart', 'Hand Cart'),
        ('bicycle', 'Bicycle'),
    ]

    STATUS_CHOICES = [
        ('available', 'Available'),
        ('on_route', 'On Route'),
        ('break', 'On Break'),
        ('offline', 'Offline'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='collector_profile')
    employee_id = models.CharField(max_length=20, unique=True)
    vehicle_type = models.CharField(max_length=20, choices=VEHICLE_CHOICES, default='truck')
    vehicle_number = models.CharField(max_length=20, blank=True)
    license_number = models.CharField(max_length=30, blank=True)
    license_expiry = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='offline')
    assigned_divisions = models.JSONField(default=list)
    capacity_kg = models.PositiveIntegerField(default=1000)
    current_load_kg = models.PositiveIntegerField(default=0)
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.00)
    total_collections = models.PositiveIntegerField(default=0)
    verified_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='verified_collectors'
    )
    id_document = models.FileField(upload_to='collector_docs/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'accounts_collector_profile'

    def __str__(self):
        return f"{self.user.get_display_name()} — Collector #{self.employee_id}"

    @property
    def load_percentage(self):
        if self.capacity_kg:
            return round((self.current_load_kg / self.capacity_kg) * 100, 1)
        return 0


class Subscription(models.Model):
    """Resident subscription plans"""
    PLAN_CHOICES = [
        ('free', 'Free (Pay-per-pickup)'),
        ('monthly', 'Monthly Plan'),
        ('quarterly', 'Quarterly Plan'),
        ('annual', 'Annual Plan'),
    ]

    STATUS_CHOICES = [
        ('active', 'Active'),
        ('expired', 'Expired'),
        ('cancelled', 'Cancelled'),
        ('pending', 'Pending Payment'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='subscriptions')
    plan = models.CharField(max_length=20, choices=PLAN_CHOICES, default='free')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    auto_renew = models.BooleanField(default=False)
    pickup_quota = models.PositiveIntegerField(default=0)  # 0 = unlimited
    pickups_used = models.PositiveIntegerField(default=0)
    payment = models.ForeignKey(
        'payments.Payment', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='subscriptions'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'accounts_subscription'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user} — {self.get_plan_display()} ({self.status})"

    @property
    def is_active(self):
        if self.status != 'active':
            return False
        if self.end_date and self.end_date < timezone.now().date():
            return False
        return True

    @property
    def days_remaining(self):
        if self.end_date:
            delta = (self.end_date - timezone.now().date()).days
            return max(0, delta)
        return None


class AuditLog(models.Model):
    """System-wide audit trail"""
    ACTION_CHOICES = [
        ('login', 'Login'),
        ('logout', 'Logout'),
        ('create', 'Create'),
        ('update', 'Update'),
        ('delete', 'Delete'),
        ('payment', 'Payment'),
        ('assign', 'Assign'),
        ('status_change', 'Status Change'),
        ('export', 'Export'),
        ('permission_change', 'Permission Change'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='audit_logs')
    action = models.CharField(max_length=30, choices=ACTION_CHOICES, db_index=True)
    model_name = models.CharField(max_length=50, blank=True)
    object_id = models.CharField(max_length=100, blank=True)
    description = models.TextField()
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    metadata = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'accounts_audit_log'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'action']),
            models.Index(fields=['created_at', 'action']),
        ]

    def __str__(self):
        return f"{self.user} — {self.action} at {self.created_at}"
