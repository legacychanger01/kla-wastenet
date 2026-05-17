"""
KLA WasteNet Pro — Waste App Celery Tasks
"""
import logging
from datetime import date, timedelta
from celery import shared_task
from django.db.models import Count, Q
from django.utils import timezone

logger = logging.getLogger('apps.waste.tasks')


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def check_smart_bins(self):
    """Alert admins when smart bins reach critical fill levels"""
    try:
        from apps.waste.models import SmartBin
        from apps.notifications.services.notifier import notification_service
        critical_bins = SmartBin.objects.filter(is_active=True, fill_level__gte=80)
        alerted = 0
        for bin_obj in critical_bins:
            try:
                notification_service.smart_bin_full(bin_obj)
                alerted += 1
            except Exception as e:
                logger.warning(f"Alert failed for bin {bin_obj.bin_id}: {e}")
        logger.info(f"Smart bin check: {alerted} critical alerts sent")
        return {'alerted': alerted}
    except Exception as exc:
        logger.error(f"check_smart_bins failed: {exc}")
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=2)
def auto_assign_pending_requests(self):
    """Auto-assign pending requests to least-loaded available collectors"""
    try:
        from apps.waste.models import PickupRequest, Assignment
        from apps.accounts.models import User
        from apps.notifications.services.notifier import notification_service

        cutoff = timezone.now() - timedelta(hours=2)
        pending = PickupRequest.objects.filter(
            status='pending', created_at__lte=cutoff
        ).select_related('user', 'category')

        assigned_count = 0
        for request in pending:
            collector = User.objects.filter(
                role='collector', is_active=True, division=request.division
            ).annotate(
                today_load=Count('assignments', filter=Q(
                    assignments__scheduled_date=date.today()
                ))
            ).order_by('today_load').first()

            if not collector:
                collector = User.objects.filter(
                    role='collector', is_active=True
                ).annotate(
                    today_load=Count('assignments', filter=Q(
                        assignments__scheduled_date=date.today()
                    ))
                ).order_by('today_load').first()

            if collector:
                assignment = Assignment.objects.create(
                    pickup_request=request,
                    collector=collector,
                    scheduled_date=date.today(),
                )
                request.status = 'assigned'
                request.save(update_fields=['status'])
                try:
                    notification_service.pickup_assigned(assignment)
                    notification_service.collector_new_assignment(assignment)
                except Exception as e:
                    logger.warning(f"Notification error: {e}")
                assigned_count += 1

        logger.info(f"Auto-assign: {assigned_count} requests assigned")
        return {'assigned': assigned_count}
    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task
def generate_morning_routes():
    """Generate optimized routes for today's assignments"""
    try:
        from apps.waste.models import Assignment, CollectionRoute
        from apps.analytics.services.ai_engine import route_optimizer

        today = date.today()
        assignments = Assignment.objects.filter(
            scheduled_date=today, route__isnull=True
        ).select_related('pickup_request', 'collector')

        collectors = {}
        for a in assignments:
            if a.collector_id:
                cid = str(a.collector_id)
                collectors.setdefault(cid, {'collector': a.collector, 'assignments': []})
                collectors[cid]['assignments'].append(a)

        routes_created = 0
        for cid, data in collectors.items():
            c = data['collector']
            c_assignments = data['assignments']
            if not c_assignments:
                continue
            ordered_ids = route_optimizer.optimize_route(c_assignments)
            metrics = route_optimizer.estimate_route_metrics(c_assignments)
            route = CollectionRoute.objects.create(
                name=f"{c.get_display_name()} Route — {today}",
                collector=c,
                division=c_assignments[0].pickup_request.division,
                date=today,
                total_stops=len(c_assignments),
                total_distance_km=metrics['total_distance_km'],
                estimated_duration_mins=metrics['estimated_duration_mins'],
            )
            for i, aid in enumerate(ordered_ids):
                Assignment.objects.filter(pk=aid).update(route=route, route_order=i)
            routes_created += 1

        return {'routes_created': routes_created, 'date': str(today)}
    except Exception as exc:
        logger.error(f"generate_morning_routes failed: {exc}")
        raise


@shared_task
def mark_overdue_requests():
    """Escalate priority on overdue pending requests"""
    try:
        from apps.waste.models import PickupRequest
        yesterday = date.today() - timedelta(days=1)
        overdue = PickupRequest.objects.filter(
            status__in=('pending', 'assigned'),
            preferred_date__lt=yesterday,
        )
        count = overdue.count()
        overdue.filter(status='pending').update(priority='high')
        logger.info(f"Marked {count} overdue requests")
        return {'overdue_count': count}
    except Exception as exc:
        logger.error(f"mark_overdue_requests failed: {exc}")
        raise


@shared_task
def cleanup_location_history():
    """Delete GPS records older than 30 days"""
    try:
        from apps.waste.models import CollectorLocationUpdate
        cutoff = timezone.now() - timedelta(days=30)
        deleted, _ = CollectorLocationUpdate.objects.filter(timestamp__lt=cutoff).delete()
        logger.info(f"Cleaned {deleted} old location records")
        return {'deleted': deleted}
    except Exception as exc:
        logger.error(f"cleanup_location_history failed: {exc}")
        raise
