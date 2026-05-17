"""
KLA WasteNet Pro — Payments Models
MTN Mobile Money, Airtel Money, Flutterwave, Pesapal integration
"""
import uuid
from django.db import models
from django.utils import timezone


class Payment(models.Model):
    GATEWAY_CHOICES = [
        ('mtn_momo', 'MTN Mobile Money'),
        ('airtel_money', 'Airtel Money'),
        ('flutterwave', 'Flutterwave'),
        ('pesapal', 'Pesapal'),
        ('cash', 'Cash'),
        ('bank', 'Bank Transfer'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('successful', 'Successful'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
        ('refunded', 'Refunded'),
        ('disputed', 'Disputed'),
    ]

    TYPE_CHOICES = [
        ('pickup', 'Pickup Payment'),
        ('subscription', 'Subscription'),
        ('recycling_reward', 'Recycling Reward'),
        ('penalty', 'Penalty'),
        ('refund', 'Refund'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reference = models.CharField(max_length=60, unique=True, blank=True)
    user = models.ForeignKey(
        'accounts.User', on_delete=models.CASCADE, related_name='payments'
    )
    payment_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='pickup')
    gateway = models.CharField(max_length=20, choices=GATEWAY_CHOICES)

    # Amounts
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=5, default='UGX')
    fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    net_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', db_index=True)

    # Phone number used for payment
    phone_number = models.CharField(max_length=20, blank=True)

    # Gateway Data
    gateway_reference = models.CharField(max_length=200, blank=True)
    gateway_response = models.JSONField(default=dict)
    gateway_status = models.CharField(max_length=50, blank=True)
    external_id = models.CharField(max_length=200, blank=True)

    # Verification
    verified = models.BooleanField(default=False)
    verified_at = models.DateTimeField(null=True, blank=True)
    verification_response = models.JSONField(default=dict)

    # Metadata
    description = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'payments_payment'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['gateway', 'status']),
            models.Index(fields=['created_at', 'status']),
            models.Index(fields=['reference']),
        ]

    def save(self, *args, **kwargs):
        if not self.reference:
            import datetime
            now = datetime.datetime.now()
            self.reference = f"KLA{now.strftime('%y%m%d')}{str(uuid.uuid4().hex[:8]).upper()}"
        if not self.net_amount:
            self.net_amount = self.amount - self.fee
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Payment {self.reference} — {self.user} ({self.amount} {self.currency})"

    @property
    def is_successful(self):
        return self.status == 'successful'


class PaymentWebhook(models.Model):
    """Store raw webhook payloads for audit and replay"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    gateway = models.CharField(max_length=20)
    event_type = models.CharField(max_length=100)
    payload = models.JSONField()
    headers = models.JSONField(default=dict)
    payment = models.ForeignKey(
        Payment, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='webhooks'
    )
    processed = models.BooleanField(default=False)
    processed_at = models.DateTimeField(null=True, blank=True)
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'payments_webhook'
        ordering = ['-created_at']

    def __str__(self):
        return f"Webhook {self.gateway}/{self.event_type} — {'processed' if self.processed else 'pending'}"


class Invoice(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('sent', 'Sent'),
        ('paid', 'Paid'),
        ('overdue', 'Overdue'),
        ('cancelled', 'Cancelled'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    invoice_number = models.CharField(max_length=30, unique=True, blank=True)
    user = models.ForeignKey(
        'accounts.User', on_delete=models.CASCADE, related_name='invoices'
    )
    payment = models.OneToOneField(
        Payment, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='invoice'
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    line_items = models.JSONField(default=list)
    due_date = models.DateField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'payments_invoice'
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.invoice_number:
            import datetime
            count = Invoice.objects.count() + 1
            year = datetime.date.today().strftime('%Y')
            self.invoice_number = f"INV-{year}-{count:06d}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Invoice {self.invoice_number} — {self.user}"
