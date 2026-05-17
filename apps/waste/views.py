"""KLA WasteNet Pro — Waste Management Views"""
import json
import logging
from datetime import date, timedelta
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum, Avg
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.conf import settings

from apps.waste.models import (
    PickupRequest, WasteCategory, Assignment,
    CollectionRoute, CollectorLocationUpdate, SmartBin, WasteReport
)
from apps.accounts.models import User
from apps.accounts.views import role_required, redirect_by_role

logger = logging.getLogger('apps.waste')


# ─── Resident Waste Views ─────────────────────────────────────────────────────

@role_required('resident', 'recycler')
def make_request(request):
    categories = WasteCategory.objects.filter(is_active=True)

    if request.method == 'POST':
        cat_id = request.POST.get('category')
        category = get_object_or_404(WasteCategory, pk=cat_id)

        pickup = PickupRequest(
            user=request.user,
            category=category,
            division=request.POST.get('division', request.user.division),
            address=request.POST.get('address', ''),
            location_instructions=request.POST.get('location_instructions', ''),
            waste_description=request.POST.get('waste_description', ''),
            preferred_date=request.POST.get('preferred_date') or None,
            priority=request.POST.get('priority', 'normal'),
            quantity=int(request.POST.get('quantity', 1)),
        )

        lat = request.POST.get('latitude')
        lng = request.POST.get('longitude')
        if lat and lng:
            pickup.latitude = lat
            pickup.longitude = lng

        if 'waste_image' in request.FILES:
            pickup.waste_image = request.FILES['waste_image']

        pickup.save()

        # Notify
        try:
            from apps.notifications.services.notifier import notification_service
            notification_service.pickup_submitted(pickup)
        except Exception as e:
            logger.warning(f"Notification failed: {e}")

        messages.success(request, f'Pickup request #{pickup.request_number} submitted successfully!')
        return redirect('my_requests')

    return render(request, 'resident/make_request.html', {
        'categories': categories,
        'DIVISIONS': User.DIVISION_CHOICES,
        'GOOGLE_MAPS_KEY': settings.GOOGLE_MAPS_API_KEY,
        'user_address': request.user.address,
        'user_division': request.user.division,
    })


@role_required('resident', 'recycler')
def my_requests(request):
    status_filter = request.GET.get('status', '')
    qs = PickupRequest.objects.filter(user=request.user).select_related(
        'category', 'assignment__collector'
    )
    if status_filter:
        qs = qs.filter(status=status_filter)

    paginator = Paginator(qs.order_by('-created_at'), 10)
    page = request.GET.get('page', 1)

    return render(request, 'resident/my_requests.html', {
        'requests': paginator.get_page(page),
        'status_filter': status_filter,
        'STATUS_CHOICES': PickupRequest.STATUS_CHOICES,
    })


@login_required
def request_detail(request, pk):
    if request.user.is_resident():
        pickup = get_object_or_404(PickupRequest, pk=pk, user=request.user)
    elif request.user.is_collector():
        pickup = get_object_or_404(PickupRequest, pk=pk, assignment__collector=request.user)
    else:
        pickup = get_object_or_404(PickupRequest, pk=pk)

    assignment = getattr(pickup, 'assignment', None)

    return render(request, 'resident/request_detail.html', {
        'pickup': pickup,
        'assignment': assignment,
        'GOOGLE_MAPS_KEY': settings.GOOGLE_MAPS_API_KEY,
    })


@login_required
@require_POST
def submit_rating(request, pk):
    pickup = get_object_or_404(PickupRequest, pk=pk, user=request.user)
    if pickup.status != 'collected':
        messages.error(request, 'You can only rate completed pickups.')
        return redirect('request_detail', pk=pk)

    rating = int(request.POST.get('rating', 0))
    feedback = request.POST.get('feedback', '')

    if 1 <= rating <= 5:
        pickup.resident_rating = rating
        pickup.resident_feedback = feedback
        pickup.rated_at = timezone.now()
        pickup.save(update_fields=['resident_rating', 'resident_feedback', 'rated_at'])
        messages.success(request, 'Thank you for your feedback!')
    else:
        messages.error(request, 'Invalid rating.')

    return redirect('request_detail', pk=pk)


# ─── Collector Views ──────────────────────────────────────────────────────────

@role_required('collector')
def update_pickup_status(request, pk):
    assignment = get_object_or_404(Assignment, pk=pk, collector=request.user)
    pickup = assignment.pickup_request

    if request.method == 'POST':
        new_status = request.POST.get('status')
        if new_status in ('in_progress', 'collected'):
            pickup.status = new_status

            if new_status == 'collected':
                assignment.completed_at = timezone.now()
                pickup.collected_at = timezone.now()
                assignment.collector_notes = request.POST.get('notes', '')
                weight = request.POST.get('weight_kg')
                if weight:
                    assignment.weight_collected_kg = weight

                if 'collection_image' in request.FILES:
                    assignment.collection_image = request.FILES['collection_image']

                if hasattr(request.user, 'collector_profile'):
                    request.user.collector_profile.total_collections += 1
                    request.user.collector_profile.save(update_fields=['total_collections'])

            pickup.save()
            assignment.save()

            try:
                from apps.notifications.services.notifier import notification_service
                if new_status == 'collected':
                    notification_service.pickup_completed(pickup)
            except Exception:
                pass

            messages.success(request, f'Status updated to {pickup.get_status_display()}.')
            return redirect('collector_dashboard')

    return render(request, 'collector/update_status.html', {
        'assignment': assignment,
        'pickup': pickup,
    })


@role_required('collector')
def update_my_location(request):
    """AJAX endpoint for collectors to update their GPS location"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            lat = data.get('latitude')
            lng = data.get('longitude')

            if lat and lng:
                request.user.update_location(lat, lng)

                # Save to history
                CollectorLocationUpdate.objects.create(
                    collector=request.user,
                    latitude=lat,
                    longitude=lng,
                    speed_kmh=data.get('speed'),
                    heading=data.get('heading'),
                    accuracy_meters=data.get('accuracy'),
                )

                # Broadcast via WebSocket (if channels configured)
                try:
                    from channels.layers import get_channel_layer
                    from asgiref.sync import async_to_sync
                    channel_layer = get_channel_layer()
                    async_to_sync(channel_layer.group_send)(
                        f'tracker_{request.user.id}',
                        {
                            'type': 'location.update',
                            'collector_id': str(request.user.id),
                            'latitude': float(lat),
                            'longitude': float(lng),
                        }
                    )
                except Exception:
                    pass

                return JsonResponse({'status': 'ok'})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)

    return JsonResponse({'error': 'Method not allowed'}, status=405)


# ─── Admin Waste Management ───────────────────────────────────────────────────

@role_required('admin', 'super_admin', 'kcca_official')
def manage_requests(request):
    status_filter = request.GET.get('status', '')
    division_filter = request.GET.get('division', '')
    search = request.GET.get('search', '')

    qs = PickupRequest.objects.select_related('user', 'category', 'assignment__collector')

    if status_filter:
        qs = qs.filter(status=status_filter)
    if division_filter:
        qs = qs.filter(division=division_filter)
    if search:
        qs = qs.filter(
            Q(request_number__icontains=search) |
            Q(user__first_name__icontains=search) |
            Q(user__last_name__icontains=search) |
            Q(address__icontains=search)
        )

    qs = qs.order_by('-created_at')
    paginator = Paginator(qs, 20)
    page = request.GET.get('page', 1)

    return render(request, 'admin/manage_requests.html', {
        'requests': paginator.get_page(page),
        'status_filter': status_filter,
        'division_filter': division_filter,
        'search': search,
        'STATUS_CHOICES': PickupRequest.STATUS_CHOICES,
        'DIVISIONS': User.DIVISION_CHOICES,
        'total_count': qs.count(),
    })


@role_required('admin', 'super_admin')
def assign_request(request, pk):
    pickup = get_object_or_404(PickupRequest, pk=pk)
    collectors = User.objects.filter(role='collector', is_active=True).select_related('collector_profile')

    if request.method == 'POST':
        collector_id = request.POST.get('collector')
        scheduled_date = request.POST.get('scheduled_date') or None

        collector = get_object_or_404(User, pk=collector_id, role='collector')

        # Remove existing assignment
        Assignment.objects.filter(pickup_request=pickup).delete()

        assignment = Assignment.objects.create(
            pickup_request=pickup,
            collector=collector,
            assigned_by=request.user,
            scheduled_date=scheduled_date,
        )

        pickup.status = 'assigned'
        pickup.save(update_fields=['status'])

        try:
            from apps.notifications.services.notifier import notification_service
            notification_service.pickup_assigned(assignment)
            notification_service.collector_new_assignment(assignment)
        except Exception as e:
            logger.warning(f"Notification failed: {e}")

        from apps.accounts.models import AuditLog
        AuditLog.objects.create(
            user=request.user, action='assign',
            description=f"Assigned #{pickup.request_number} to {collector.get_display_name()}",
            ip_address=request.META.get('REMOTE_ADDR'),
        )

        messages.success(request, f'Request #{pickup.request_number} assigned to {collector.get_display_name()}.')
        return redirect('manage_requests')

    return render(request, 'admin/assign_request.html', {
        'pickup': pickup,
        'collectors': collectors,
    })


@role_required('admin', 'super_admin', 'kcca_official')
def reports_view(request):
    from django.db.models.functions import TruncMonth
    from apps.payments.models import Payment

    today = date.today()
    month_start = today.replace(day=1)

    zone_stats = list(
        PickupRequest.objects.values('division')
        .annotate(
            total=Count('id'),
            collected=Count('id', filter=Q(status='collected')),
            pending=Count('id', filter=Q(status='pending')),
            cancelled=Count('id', filter=Q(status='cancelled')),
            revenue=Sum('payment__amount', filter=Q(payment__status='successful')),
        )
        .order_by('division')
    )

    category_stats = list(
        PickupRequest.objects.values('category__name', 'category__icon', 'category__color')
        .annotate(
            total=Count('id'),
            collected=Count('id', filter=Q(status='collected')),
        )
        .order_by('-total')
    )

    collector_stats = list(
        User.objects.filter(role='collector')
        .annotate(
            total_assigned=Count('assignments'),
            total_collected=Count('assignments', filter=Q(
                assignments__pickup_request__status='collected'
            )),
            avg_rating=Avg('assignments__pickup_request__resident_rating'),
        )
        .order_by('-total_collected')
    )

    monthly_revenue = list(
        Payment.objects.filter(status='successful')
        .annotate(month=TruncMonth('created_at'))
        .values('month')
        .annotate(total=Sum('amount'), count=Count('id'))
        .order_by('month')
    )

    return render(request, 'admin/reports.html', {
        'zone_stats': zone_stats,
        'category_stats': category_stats,
        'collector_stats': collector_stats,
        'monthly_revenue': monthly_revenue,
    })


@role_required('admin', 'super_admin', 'kcca_official')
def export_report(request, format_type):
    """Export reports as PDF, Excel, or CSV"""
    from apps.analytics.services.exporter import ReportExporter

    report_type = request.GET.get('type', 'requests')
    exporter = ReportExporter()

    if format_type == 'csv':
        return exporter.export_csv(report_type)
    elif format_type == 'excel':
        return exporter.export_excel(report_type)
    elif format_type == 'pdf':
        return exporter.export_pdf(report_type)

    messages.error(request, 'Invalid export format.')
    return redirect('reports')


# ─── Smart Bins ───────────────────────────────────────────────────────────────

@role_required('admin', 'super_admin', 'kcca_official')
def smart_bins_view(request):
    division_filter = request.GET.get('division', '')
    qs = SmartBin.objects.filter(is_active=True)
    if division_filter:
        qs = qs.filter(division=division_filter)

    bins_data = list(qs.values(
        'id', 'bin_id', 'location_name', 'division',
        'latitude', 'longitude', 'fill_level', 'status', 'last_emptied'
    ))

    return render(request, 'admin/smart_bins.html', {
        'bins': qs,
        'bins_json': json.dumps(bins_data, default=str),
        'division_filter': division_filter,
        'GOOGLE_MAPS_KEY': settings.GOOGLE_MAPS_API_KEY,
        'DIVISIONS': User.DIVISION_CHOICES,
        'critical_count': qs.filter(fill_level__gte=80).count(),
    })


# ─── Route Management ─────────────────────────────────────────────────────────

@role_required('admin', 'super_admin')
def optimize_routes(request):
    """Generate optimized routes for today's assignments"""
    from apps.analytics.services.ai_engine import route_optimizer

    today = date.today()
    division = request.GET.get('division', '')

    # Get unrouted assignments for today
    assignments_qs = Assignment.objects.filter(
        scheduled_date=today,
        route__isnull=True,
        pickup_request__status='assigned'
    ).select_related('pickup_request', 'collector')

    if division:
        assignments_qs = assignments_qs.filter(pickup_request__division=division)

    # Group by collector
    collectors = {}
    for a in assignments_qs:
        cid = str(a.collector_id) if a.collector_id else None
        if cid:
            collectors.setdefault(cid, {'collector': a.collector, 'assignments': []})
            collectors[cid]['assignments'].append(a)

    routes_created = 0
    for cid, data in collectors.items():
        collector = data['collector']
        assignments = data['assignments']

        if not assignments:
            continue

        ordered_ids = route_optimizer.optimize_route(assignments)
        metrics = route_optimizer.estimate_route_metrics(assignments)

        route = CollectionRoute.objects.create(
            name=f"Route {collector.get_display_name()} - {today}",
            collector=collector,
            division=division or 'all',
            date=today,
            total_stops=len(assignments),
            total_distance_km=metrics['total_distance_km'],
            estimated_duration_mins=metrics['estimated_duration_mins'],
        )

        for i, assignment_id in enumerate(ordered_ids):
            Assignment.objects.filter(pk=assignment_id).update(
                route=route, route_order=i
            )

        routes_created += 1

    messages.success(request, f'Created {routes_created} optimized routes for {today}.')
    return redirect('admin_dashboard')
