"""KLA WasteNet Pro — Recycling Models"""
import uuid
from django.db import models


class RecyclingRequest(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('collected', 'Collected'),
        ('processed', 'Processed'),
        ('rewarded', 'Rewarded'),
    ]

    MATERIAL_CHOICES = [
        ('plastic', 'Plastic'),
        ('paper', 'Paper/Cardboard'),
        ('glass', 'Glass'),
        ('metal', 'Metal/Aluminium'),
        ('electronics', 'E-Waste'),
        ('organic', 'Organic/Compost'),
        ('textile', 'Textiles'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey('accounts.User', on_delete=models.CASCADE, related_name='recycling_requests')
    material_type = models.CharField(max_length=20, choices=MATERIAL_CHOICES)
    estimated_weight_kg = models.DecimalField(max_digits=6, decimal_places=2)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to='recycling/', blank=True, null=True)
    address = models.TextField()
    division = models.CharField(max_length=50)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    recycler = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='assigned_recycling', limit_choices_to={'role': 'recycler'}
    )
    actual_weight_kg = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    reward_points = models.PositiveIntegerField(default=0)
    reward_paid = models.BooleanField(default=False)
    carbon_saved_kg = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    preferred_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    collected_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'recycling_request'
        ordering = ['-created_at']

    def __str__(self):
        return f"Recycling: {self.material_type} by {self.user}"


class RewardPoints(models.Model):
    """Resident recycling reward points ledger"""
    TRANSACTION_CHOICES = [
        ('earned', 'Earned'),
        ('redeemed', 'Redeemed'),
        ('expired', 'Expired'),
        ('bonus', 'Bonus'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey('accounts.User', on_delete=models.CASCADE, related_name='reward_transactions')
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_CHOICES)
    points = models.IntegerField()
    balance_after = models.IntegerField()
    description = models.CharField(max_length=200)
    recycling_request = models.ForeignKey(
        RecyclingRequest, on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'recycling_reward_points'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user}: {self.points:+d} pts ({self.transaction_type})"


class EnvironmentalCampaign(models.Model):
    """KCCA environmental awareness campaigns"""
    STATUS_CHOICES = [('draft', 'Draft'), ('active', 'Active'), ('ended', 'Ended')]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200)
    description = models.TextField()
    banner_image = models.ImageField(upload_to='campaigns/', blank=True, null=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='draft')
    start_date = models.DateField()
    end_date = models.DateField()
    target_division = models.CharField(max_length=50, blank=True)
    created_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'recycling_campaign'
        ordering = ['-created_at']

    def __str__(self):
        return self.title
