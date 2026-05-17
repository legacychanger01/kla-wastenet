"""KLA WasteNet Pro — Notification Model"""
import uuid
from django.db import models


class Notification(models.Model):
    TYPE_CHOICES = [
        ('pickup_submitted', 'Pickup Submitted'),
        ('pickup_assigned', 'Pickup Assigned'),
        ('pickup_completed', 'Pickup Completed'),
        ('payment_confirmed', 'Payment Confirmed'),
        ('subscription_expiring', 'Subscription Expiring'),
        ('system', 'System Notification'),
        ('announcement', 'Announcement'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        'accounts.User', on_delete=models.CASCADE, related_name='notifications'
    )
    notification_type = models.CharField(max_length=30, choices=TYPE_CHOICES)
    title = models.CharField(max_length=200)
    message = models.TextField()
    action_url = models.URLField(blank=True)
    is_read = models.BooleanField(default=False, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'notifications_notification'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_read']),
        ]

    def __str__(self):
        return f"{self.user} — {self.title}"

    def mark_read(self):
        from django.utils import timezone
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=['is_read', 'read_at'])
