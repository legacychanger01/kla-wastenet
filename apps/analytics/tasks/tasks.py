"""
KLA WasteNet Pro — Analytics Celery Tasks
"""
import logging
from celery import shared_task

logger = logging.getLogger('apps.analytics.tasks')


@shared_task
def generate_daily_predictions():
    """Generate AI demand predictions for all divisions"""
    try:
        from apps.analytics.services.ai_engine import demand_predictor
        from apps.accounts.models import User

        divisions = [val for val, _ in User.DIVISION_CHOICES]
        results = {}

        for division in divisions:
            predictions = demand_predictor.predict_division_demand(division, days_ahead=7)
            results[division] = predictions
            logger.info(f"Predictions for {division}: {predictions[:2]}")

        logger.info(f"Daily predictions generated for {len(divisions)} divisions")
        return {'divisions': len(divisions), 'success': True}

    except Exception as exc:
        logger.error(f"generate_daily_predictions failed: {exc}")
        raise


@shared_task
def send_weekly_report():
    """Email a weekly summary report to KCCA officials"""
    try:
        from apps.accounts.models import User
        from apps.analytics.services.ai_engine import analytics_dashboard
        from apps.notifications.services.notifier import EmailService

        officials = User.objects.filter(
            role__in=['kcca_official', 'super_admin'],
            is_active=True,
            email__isnull=False,
        )

        overview = analytics_dashboard.get_overview_stats()
        collector_perf = analytics_dashboard.get_collector_performance()
        email_svc = EmailService()

        for official in officials:
            try:
                email_svc.send(
                    user=official,
                    subject="Weekly Operations Report",
                    template_name="weekly_report",
                    context={
                        'overview': overview,
                        'collector_perf': collector_perf[:5],
                    }
                )
            except Exception as e:
                logger.warning(f"Weekly report email failed for {official.email}: {e}")

        logger.info(f"Weekly report sent to {officials.count()} officials")
        return {'sent': officials.count()}

    except Exception as exc:
        logger.error(f"send_weekly_report failed: {exc}")
        raise
