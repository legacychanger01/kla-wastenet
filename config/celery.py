"""
KLA WasteNet Pro — Celery Configuration
Background task processing for notifications, payments, analytics
"""
import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.production')

app = Celery('kla_wastenet')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

# ── Periodic Tasks (Beat Schedule) ────────────────────────────────────────────
app.conf.beat_schedule = {

    # Check pending payments every 5 minutes
    'verify-pending-payments': {
        'task': 'apps.payments.tasks.verify_pending_payments',
        'schedule': crontab(minute='*/5'),
    },

    # Send subscription expiry reminders daily at 8 AM
    'subscription-expiry-reminders': {
        'task': 'apps.accounts.tasks.send_subscription_reminders',
        'schedule': crontab(hour=8, minute=0),
    },

    # Generate AI demand predictions daily at 6 AM
    'generate-demand-predictions': {
        'task': 'apps.analytics.tasks.generate_daily_predictions',
        'schedule': crontab(hour=6, minute=0),
    },

    # Smart bin alerts every 30 minutes
    'smart-bin-alerts': {
        'task': 'apps.waste.tasks.check_smart_bins',
        'schedule': crontab(minute='*/30'),
    },

    # Auto-assign unassigned requests every hour
    'auto-assign-requests': {
        'task': 'apps.waste.tasks.auto_assign_pending_requests',
        'schedule': crontab(minute=0),
    },

    # Generate optimized routes daily at 5:30 AM
    'generate-daily-routes': {
        'task': 'apps.waste.tasks.generate_morning_routes',
        'schedule': crontab(hour=5, minute=30),
    },

    # Clean old location tracking records daily at midnight
    'cleanup-old-locations': {
        'task': 'apps.waste.tasks.cleanup_location_history',
        'schedule': crontab(hour=0, minute=0),
    },

    # Send weekly analytics report every Monday at 7 AM
    'weekly-analytics-report': {
        'task': 'apps.analytics.tasks.send_weekly_report',
        'schedule': crontab(hour=7, minute=0, day_of_week=1),
    },

    # Mark overdue requests daily at 9 AM
    'mark-overdue-requests': {
        'task': 'apps.waste.tasks.mark_overdue_requests',
        'schedule': crontab(hour=9, minute=0),
    },
}

app.conf.task_routes = {
    'apps.payments.*': {'queue': 'payments'},
    'apps.notifications.*': {'queue': 'notifications'},
    'apps.analytics.*': {'queue': 'analytics'},
    'apps.waste.*': {'queue': 'default'},
    'apps.accounts.*': {'queue': 'default'},
}

app.conf.task_serializer = 'json'
app.conf.result_serializer = 'json'
app.conf.accept_content = ['json']
app.conf.timezone = 'Africa/Kampala'
app.conf.enable_utc = True
app.conf.task_track_started = True
app.conf.task_acks_late = True
app.conf.worker_prefetch_multiplier = 1
