"""KLA WasteNet Pro — Support Ticket Models"""
import uuid
from django.db import models


class SupportTicket(models.Model):
    CATEGORY_CHOICES = [
        ('payment', 'Payment Issue'),
        ('pickup', 'Pickup Problem'),
        ('account', 'Account Issue'),
        ('app', 'App/Technical'),
        ('complaint', 'Complaint'),
        ('other', 'Other'),
    ]

    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]

    STATUS_CHOICES = [
        ('open', 'Open'),
        ('in_progress', 'In Progress'),
        ('waiting_customer', 'Waiting for Customer'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ticket_number = models.CharField(max_length=20, unique=True, blank=True)
    user = models.ForeignKey('accounts.User', on_delete=models.CASCADE, related_name='support_tickets')
    assigned_to = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='assigned_tickets'
    )
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium')
    subject = models.CharField(max_length=200)
    description = models.TextField()
    attachment = models.FileField(upload_to='ticket_attachments/', blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    resolution = models.TextField(blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'support_ticket'
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.ticket_number:
            import datetime
            count = SupportTicket.objects.count() + 1
            self.ticket_number = f"TKT{datetime.date.today().strftime('%y%m')}{count:05d}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Ticket {self.ticket_number}: {self.subject}"


class TicketMessage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ticket = models.ForeignKey(SupportTicket, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey('accounts.User', on_delete=models.CASCADE)
    message = models.TextField()
    attachment = models.FileField(upload_to='ticket_messages/', blank=True, null=True)
    is_internal = models.BooleanField(default=False)  # Internal staff notes
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'support_ticket_message'
        ordering = ['created_at']

    def __str__(self):
        return f"Message on {self.ticket.ticket_number} by {self.sender}"
