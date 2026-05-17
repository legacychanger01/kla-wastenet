"""
KLA WasteNet Pro — Waste Management Models
Core waste pickup, assignment, scheduling, and GPS tracking
"""
import uuid
from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator


class WasteCategory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, default='🗑️')
    color = models.CharField(max_length=7, default='#4CAF50')
    base_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_hazardous = models.BooleanField(default=False)
    requires_special_handling = models.BooleanField(default=False)
    is_recyclable = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'waste_category'
        ordering = ['sort_order', 'name']
        verbose_name_plural = 'Waste Categories'

    def __str__(self):
        return self.name


class SmartBin(models.Model):
    """IoT Smart Bin monitoring"""
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('full', 'Full'),
        ('maintenance', 'Under Maintenance'),
        ('offline', 'Offline'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    bin_id = models.CharField(max_length=30, unique=True)
    location_name = models.CharField(max_length=200)
    division = models.CharField(max_length=50)
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    capacity_liters = models.PositiveIntegerField(default=240)
    fill_level = models.PositiveIntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    waste_category = models.ForeignKey(WasteCategory, on_delete=models.SET_NULL, null=True)
    last_emptied = models.DateTimeField(null=True, blank=True)
    last_reading = models.DateTimeField(null=True, blank=True)
    sensor_data = models.JSONField(default=dict)  # temperature, weight, etc.
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'waste_smart_bin'
        indexes = [
            models.Index(fields=['division', 'status']),
            models.Index(fields=['fill_level']),
        ]

    def __str__(self):
        return f"Bin {self.bin_id} — {self.location_name} ({self.fill_level}%)"

    @property
    def needs_collection(self):
        return self.fill_level >= 80


class PickupRequest(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('assigned', 'Assigned'),
        ('in_progress', 'In Progress'),
        ('collected', 'Collected'),
        ('cancelled', 'Cancelled'),
        ('rescheduled', 'Rescheduled'),
    ]

    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('normal', 'Normal'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]

    DIVISION_CHOICES = [
        ('central', 'Central Division'),
        ('kawempe', 'Kawempe Division'),
        ('makindye', 'Makindye Division'),
        ('nakawa', 'Nakawa Division'),
        ('rubaga', 'Rubaga Division'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    request_number = models.CharField(max_length=20, unique=True, blank=True)
    user = models.ForeignKey(
        'accounts.User', on_delete=models.CASCADE, related_name='pickup_requests'
    )
    category = models.ForeignKey(WasteCategory, on_delete=models.PROTECT)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', db_index=True)
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='normal')

    # Location
    division = models.CharField(max_length=50, choices=DIVISION_CHOICES, blank=True, db_index=True)
    address = models.TextField()
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    location_instructions = models.TextField(blank=True)

    # Waste Details
    estimated_weight_kg = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    waste_description = models.TextField(blank=True)
    waste_image = models.ImageField(upload_to='waste_images/', blank=True, null=True)
    quantity = models.PositiveIntegerField(default=1)

    # Scheduling
    preferred_date = models.DateField(null=True, blank=True)
    preferred_time_start = models.TimeField(null=True, blank=True)
    preferred_time_end = models.TimeField(null=True, blank=True)

    # Payment
    amount_due = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_paid = models.BooleanField(default=False, db_index=True)
    payment = models.ForeignKey(
        'payments.Payment', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='pickup_requests'
    )

    # Feedback
    resident_rating = models.PositiveIntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    resident_feedback = models.TextField(blank=True)
    rated_at = models.DateTimeField(null=True, blank=True)

    # Metadata
    notes = models.TextField(blank=True)
    cancellation_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    collected_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'waste_pickup_request'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'division']),
            models.Index(fields=['user', 'status']),
            models.Index(fields=['created_at', 'status']),
            models.Index(fields=['preferred_date', 'status']),
            models.Index(fields=['is_paid', 'status']),
        ]

    def save(self, *args, **kwargs):
        if not self.request_number:
            import datetime
            prefix = 'KLA'
            year = datetime.date.today().strftime('%y')
            count = PickupRequest.objects.count() + 1
            self.request_number = f"{prefix}{year}{count:06d}"
        if not self.amount_due and self.category:
            self.amount_due = self.category.base_fee
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Request #{self.request_number} — {self.user} ({self.status})"

    @property
    def is_overdue(self):
        if self.preferred_date and self.status in ('pending', 'assigned'):
            return self.preferred_date < timezone.now().date()
        return False


class Assignment(models.Model):
    """Waste collection assignment with GPS routing"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    pickup_request = models.OneToOneField(
        PickupRequest, on_delete=models.CASCADE, related_name='assignment'
    )
    collector = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True,
        related_name='assignments', limit_choices_to={'role': 'collector'}
    )
    assigned_by = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True,
        related_name='made_assignments'
    )
    route = models.ForeignKey(
        'CollectionRoute', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='assignments'
    )
    route_order = models.PositiveIntegerField(default=0)

    # Scheduling
    scheduled_date = models.DateField(null=True, blank=True)
    scheduled_time_start = models.TimeField(null=True, blank=True)
    scheduled_time_end = models.TimeField(null=True, blank=True)
    estimated_arrival = models.DateTimeField(null=True, blank=True)
    actual_arrival = models.DateTimeField(null=True, blank=True)

    # Collector Updates
    collector_notes = models.TextField(blank=True)
    collection_image = models.ImageField(upload_to='collection_proof/', blank=True, null=True)
    weight_collected_kg = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)

    assigned_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'waste_assignment'
        indexes = [
            models.Index(fields=['collector', 'scheduled_date']),
            models.Index(fields=['scheduled_date']),
        ]

    def __str__(self):
        return f"Assignment #{self.pickup_request.request_number} → {self.collector}"


class CollectionRoute(models.Model):
    """Optimized collection routes for collectors"""
    STATUS_CHOICES = [
        ('planned', 'Planned'),
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    collector = models.ForeignKey(
        'accounts.User', on_delete=models.CASCADE, related_name='routes'
    )
    division = models.CharField(max_length=50)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='planned')
    date = models.DateField()
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    total_distance_km = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    estimated_duration_mins = models.PositiveIntegerField(null=True, blank=True)
    waypoints = models.JSONField(default=list)  # Optimized waypoints
    polyline = models.TextField(blank=True)  # Encoded polyline for map
    total_stops = models.PositiveIntegerField(default=0)
    completed_stops = models.PositiveIntegerField(default=0)
    fuel_consumed_liters = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'waste_collection_route'
        ordering = ['-date']

    def __str__(self):
        return f"Route: {self.name} — {self.date} ({self.collector})"


class CollectorLocationUpdate(models.Model):
    """Real-time GPS tracking for collectors"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    collector = models.ForeignKey(
        'accounts.User', on_delete=models.CASCADE, related_name='location_updates'
    )
    assignment = models.ForeignKey(
        Assignment, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='location_updates'
    )
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    speed_kmh = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    heading = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    accuracy_meters = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        db_table = 'waste_collector_location'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['collector', 'timestamp']),
        ]

    def __str__(self):
        return f"{self.collector} @ {self.latitude},{self.longitude}"


class WasteReport(models.Model):
    """Community waste issue reporting"""
    ISSUE_TYPE_CHOICES = [
        ('illegal_dumping', 'Illegal Dumping'),
        ('overflowing_bin', 'Overflowing Bin'),
        ('missed_collection', 'Missed Collection'),
        ('road_blockage', 'Road Blockage'),
        ('hazardous_waste', 'Hazardous Waste'),
        ('other', 'Other'),
    ]

    STATUS_CHOICES = [
        ('open', 'Open'),
        ('investigating', 'Under Investigation'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reporter = models.ForeignKey(
        'accounts.User', on_delete=models.CASCADE, related_name='waste_reports'
    )
    issue_type = models.CharField(max_length=30, choices=ISSUE_TYPE_CHOICES)
    title = models.CharField(max_length=200)
    description = models.TextField()
    division = models.CharField(max_length=50)
    address = models.TextField()
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    image = models.ImageField(upload_to='waste_reports/', blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    assigned_to = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='assigned_reports'
    )
    resolution_notes = models.TextField(blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'waste_report'
        ordering = ['-created_at']

    def __str__(self):
        return f"Report: {self.title} ({self.status})"
