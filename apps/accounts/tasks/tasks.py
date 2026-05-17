"""
KLA WasteNet Pro — Accounts Celery Tasks
"""
import logging
from datetime import date, timedelta
from celery import shared_task

logger = logging.getLogger('apps.accounts.tasks')


@shared_task
def send_subscription_reminders():
    """Notify users whose subscriptions expire in 7 days or less"""
    try:
        from apps.accounts.models import Subscription
        from apps.notifications.services.notifier import notification_service

        in_7_days = date.today() + timedelta(days=7)
        expiring = Subscription.objects.filter(
            status='active',
            end_date__lte=in_7_days,
            end_date__gte=date.today(),
        ).select_related('user')

        reminded = 0
        for sub in expiring:
            try:
                days = (sub.end_date - date.today()).days
                notification_service.subscription_expiring(sub.user, days)
                reminded += 1
            except Exception as e:
                logger.warning(f"Reminder failed for {sub.user}: {e}")

        logger.info(f"Subscription reminders sent: {reminded}")
        return {'reminded': reminded}

    except Exception as exc:
        logger.error(f"send_subscription_reminders failed: {exc}")
        raise


@shared_task
def deactivate_expired_subscriptions():
    """Mark subscriptions past their end date as expired"""
    try:
        from apps.accounts.models import Subscription

        expired = Subscription.objects.filter(
            status='active',
            end_date__lt=date.today(),
        )
        count = expired.count()
        expired.update(status='expired')
        logger.info(f"Deactivated {count} expired subscriptions")
        return {'deactivated': count}

    except Exception as exc:
        logger.error(f"deactivate_expired_subscriptions failed: {exc}")
        raise
