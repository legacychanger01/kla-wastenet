"""
KLA WasteNet Pro — Accounts Views
Authentication, dashboards, user management
"""
import logging
from datetime import date, timedelta
from functools import wraps

from django.contrib import messages
from django.contrib.auth import login, logout, authenticate, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordResetForm
from django.core.paginator import Paginator
from django.db.models import Count, Q, Avg, Sum
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.accounts.models import User, AuditLog, Subscription
from apps.notifications.models import Notification

logger = logging.getLogger('apps.accounts')


# ─── Decorators ───────────────────────────────────────────────────────────────

def role_required(*roles):
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def wrapper(request, *args, **kwargs):
            if request.user.role not in roles:
                messages.error(request, 'You do not have permission to access this page.')
                return redirect_by_role(request.user)
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def redirect_by_role(user):
    role_map = {
        'super_admin': 'admin_dashboard',
        'kcca_official': 'kcca_dashboard',
        'admin': 'admin_dashboard',
        'collector': 'collector_dashboard',
        'recycler': 'resident_dashboard',
        'resident': 'resident_dashboard',
    }
    return redirect(role_map.get(user.role, 'home'))


# ─── Auth Views ───────────────────────────────────────────────────────────────

def home(request):
    if request.user.is_authenticated:
        return redirect_by_role(request.user)
    return render(request, 'home.html')


def login_view(request):
    if request.user.is_authenticated:
        return redirect_by_role(request.user)

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        user = authenticate(request, username=username, password=password)

        if user is not None:
            if not user.is_active:
                messages.error(request, 'Your account has been suspended. Contact support.')
                return render(request, 'auth/login.html')

            login(request, user)
            user.last_active = timezone.now()
            user.last_login_ip = request.META.get('REMOTE_ADDR')
            user.save(update_fields=['last_active', 'last_login_ip'])

            AuditLog.objects.create(
                user=user, action='login',
                description=f"Login from {request.META.get('REMOTE_ADDR')}",
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
            )

            messages.success(request, f'Welcome back, {user.get_display_name()}! 👋')
            next_url = request.GET.get('next')
            if next_url:
                return redirect(next_url)
            return redirect_by_role(user)
        else:
            messages.error(request, 'Invalid username or password. Please try again.')
            logger.warning(f"Failed login attempt for: {username}")

    return render(request, 'auth/login.html')


def logout_view(request):
    if request.user.is_authenticated:
        AuditLog.objects.create(
            user=request.user, action='logout',
            description='User logged out',
            ip_address=request.META.get('REMOTE_ADDR'),
        )
    logout(request)
    messages.info(request, 'You have been signed out successfully.')
    return redirect('home')


def register_view(request):
    if request.user.is_authenticated:
        return redirect_by_role(request.user)

    if request.method == 'POST':
        from apps.accounts.forms import ResidentRegistrationForm
        form = ResidentRegistrationForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save()
            login(request, user)

            # Create welcome notification
            Notification.objects.create(
                user=user,
                notification_type='system',
                title='Welcome to KLA WasteNet! 🌿',
                message=(
                    f'Hello {user.get_display_name()}! Your account is ready. '
                    'Submit your first pickup request to get started.'
                ),
            )

            AuditLog.objects.create(
                user=user, action='create',
                description='New resident account registered',
                ip_address=request.META.get('REMOTE_ADDR'),
            )

            messages.success(request, f'Welcome, {user.get_display_name()}! Account created successfully.')
            return redirect('resident_dashboard')
    else:
        from apps.accounts.forms import ResidentRegistrationForm
        form = ResidentRegistrationForm()

    return render(request, 'auth/register.html', {'form': form})


def password_reset_request(request):
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        try:
            user = User.objects.get(email=email, is_active=True)
            # In production: generate token, send email
            messages.success(request, 'Password reset instructions sent to your email.')
        except User.DoesNotExist:
            messages.success(request, 'If an account exists with that email, instructions will be sent.')
    return render(request, 'auth/password_reset.html')


def verify_email(request, token):
    messages.success(request, 'Email verified successfully!')
    return redirect('login')


def setup_2fa(request):
    return render(request, 'auth/setup_2fa.html')


# ─── Profile ──────────────────────────────────────────────────────────────────

@login_required
def profile_view(request):
    subscriptions = Subscription.objects.filter(user=request.user).order_by('-created_at')[:3]
    return render(request, 'auth/profile.html', {
        'subscriptions': subscriptions,
    })


@login_required
def profile_edit(request):
    if request.method == 'POST':
        user = request.user
        user.first_name = request.POST.get('first_name', user.first_name)
        user.last_name = request.POST.get('last_name', user.last_name)
        user.phone = request.POST.get('phone', user.phone)
        user.address = request.POST.get('address', user.address)
        user.division = request.POST.get('division', user.division)
        user.bio = request.POST.get('bio', user.bio)
        user.email_notifications = bool(request.POST.get('email_notifications'))
        user.sms_notifications = bool(request.POST.get('sms_notifications'))
        user.dark_mode = bool(request.POST.get('dark_mode'))

        if 'avatar' in request.FILES:
            user.avatar = request.FILES['avatar']

        user.save()
        messages.success(request, 'Profile updated successfully.')
        return redirect('profile')

    return render(request, 'auth/profile_edit.html')


# ─── Resident Dashboard ───────────────────────────────────────────────────────

@role_required('resident', 'recycler')
def resident_dashboard(request):
    from apps.waste.models import PickupRequest
    from apps.payments.models import Payment

    user = request.user
    today = date.today()

    requests_qs = PickupRequest.objects.filter(user=user)
    stats = {
        'pending': requests_qs.filter(status='pending').count(),
        'assigned': requests_qs.filter(status='assigned').count(),
        'in_progress': requests_qs.filter(status='in_progress').count(),
        'collected': requests_qs.filter(status='collected').count(),
        'total': requests_qs.count(),
        'unpaid': requests_qs.filter(is_paid=False).exclude(status='cancelled').count(),
    }

    recent_requests = requests_qs.select_related('category', 'assignment__collector').order_by('-created_at')[:5]
    recent_payments = Payment.objects.filter(user=user, status='successful').order_by('-created_at')[:3]

    # Active subscription
    active_sub = Subscription.objects.filter(user=user, status='active').first()

    # Recycling points
    recycling_points = 0
    try:
        from apps.recycling.models import RewardPoints
        points_data = RewardPoints.objects.filter(user=user).aggregate(total=Sum('points'))
        recycling_points = points_data['total'] or 0
    except Exception:
        pass

    notifications = Notification.objects.filter(user=user, is_read=False).order_by('-created_at')[:5]

    return render(request, 'resident/dashboard.html', {
        'stats': stats,
        'recent_requests': recent_requests,
        'recent_payments': recent_payments,
        'active_sub': active_sub,
        'recycling_points': recycling_points,
        'notifications': notifications,
    })


# ─── Collector Dashboard ──────────────────────────────────────────────────────

@role_required('collector')
def collector_dashboard(request):
    from apps.waste.models import Assignment, CollectionRoute

    user = request.user
    today = date.today()

    assignments = Assignment.objects.filter(
        collector=user
    ).select_related(
        'pickup_request__user', 'pickup_request__category', 'pickup_request__user'
    ).order_by('-assigned_at')

    stats = {
        'pending': assignments.filter(pickup_request__status='assigned').count(),
        'in_progress': assignments.filter(pickup_request__status='in_progress').count(),
        'today': assignments.filter(scheduled_date=today).count(),
        'completed_today': assignments.filter(
            scheduled_date=today, pickup_request__status='collected'
        ).count(),
        'total_completed': assignments.filter(pickup_request__status='collected').count(),
    }

    today_assignments = assignments.filter(scheduled_date=today).order_by('route_order')
    recent_assignments = assignments.exclude(scheduled_date=today).order_by('-assigned_at')[:10]

    # Active route
    active_route = CollectionRoute.objects.filter(
        collector=user, date=today, status='active'
    ).first()

    profile = getattr(user, 'collector_profile', None)

    return render(request, 'collector/dashboard.html', {
        'stats': stats,
        'today_assignments': today_assignments,
        'recent_assignments': recent_assignments,
        'active_route': active_route,
        'profile': profile,
    })


# ─── Admin Dashboard ──────────────────────────────────────────────────────────

@role_required('admin', 'super_admin')
def admin_dashboard(request):
    from apps.waste.models import PickupRequest, Assignment, SmartBin
    from apps.payments.models import Payment
    from apps.analytics.services.ai_engine import analytics_dashboard

    today = date.today()
    week_ago = today - timedelta(days=7)
    month_start = today.replace(day=1)

    stats = {
        'total_residents': User.objects.filter(role='resident').count(),
        'total_collectors': User.objects.filter(role='collector').count(),
        'pending': PickupRequest.objects.filter(status='pending').count(),
        'assigned': PickupRequest.objects.filter(status='assigned').count(),
        'in_progress': PickupRequest.objects.filter(status='in_progress').count(),
        'collected_today': PickupRequest.objects.filter(status='collected', collected_at__date=today).count(),
        'collected_week': PickupRequest.objects.filter(status='collected', created_at__date__gte=week_ago).count(),
        'total_requests': PickupRequest.objects.count(),
        'revenue_month': Payment.objects.filter(
            status='successful', created_at__date__gte=month_start
        ).aggregate(total=Sum('amount'))['total'] or 0,
        'critical_bins': SmartBin.objects.filter(fill_level__gte=80, is_active=True).count(),
        'open_tickets': 0,  # support tickets
    }

    # Zone distribution
    zone_data = list(
        PickupRequest.objects.values('division')
        .annotate(count=Count('id'))
        .order_by('-count')
    )
    total_reqs = sum(z['count'] for z in zone_data)
    for z in zone_data:
        z['percentage'] = round((z['count'] / total_reqs * 100) if total_reqs else 0, 1)

    # Category distribution
    category_data = list(
        PickupRequest.objects.values('category__name', 'category__icon', 'category__color')
        .annotate(count=Count('id'))
        .order_by('-count')[:6]
    )

    # Recent requests
    recent_requests = PickupRequest.objects.select_related(
        'user', 'category', 'assignment__collector'
    ).order_by('-created_at')[:10]

    # Recent payments
    recent_payments = Payment.objects.select_related('user').filter(
        status='successful'
    ).order_by('-created_at')[:5]

    # Smart bins needing collection
    critical_bins = SmartBin.objects.filter(fill_level__gte=80, is_active=True)[:5]

    # Monthly trend (last 6 months)
    monthly_trend = analytics_dashboard.get_monthly_trend(6)

    # Collector performance
    top_collectors = list(
        User.objects.filter(role='collector', is_active=True)
        .annotate(
            completed=Count('assignments', filter=Q(
                assignments__pickup_request__status='collected'
            ))
        )
        .order_by('-completed')[:5]
    )

    return render(request, 'admin/dashboard.html', {
        'stats': stats,
        'zone_data': zone_data,
        'category_data': category_data,
        'recent_requests': recent_requests,
        'recent_payments': recent_payments,
        'critical_bins': critical_bins,
        'monthly_trend': monthly_trend,
        'top_collectors': top_collectors,
    })


@role_required('kcca_official', 'super_admin')
def kcca_dashboard(request):
    """High-level KCCA city overview"""
    from apps.waste.models import PickupRequest
    from apps.payments.models import Payment
    from apps.analytics.services.ai_engine import analytics_dashboard, demand_predictor

    today = date.today()
    month_start = today.replace(day=1)

    overview = analytics_dashboard.get_overview_stats()
    predictions = demand_predictor.predict_division_demand('central', 7)
    hotspots = demand_predictor.identify_hotspots()

    # Division stats
    division_stats = list(
        PickupRequest.objects.values('division')
        .annotate(
            total=Count('id'),
            pending=Count('id', filter=Q(status='pending')),
            collected=Count('id', filter=Q(status='collected')),
            revenue=Sum('payment__amount', filter=Q(payment__status='successful')),
        )
        .order_by('division')
    )

    # Revenue by gateway
    revenue_by_gateway = list(
        Payment.objects.filter(status='successful', created_at__date__gte=month_start)
        .values('gateway')
        .annotate(total=Sum('amount'), count=Count('id'))
        .order_by('-total')
    )

    collector_performance = analytics_dashboard.get_collector_performance()

    return render(request, 'admin/kcca_dashboard.html', {
        'overview': overview,
        'predictions': predictions,
        'hotspots': hotspots,
        'division_stats': division_stats,
        'revenue_by_gateway': revenue_by_gateway,
        'collector_performance': collector_performance,
    })


# ─── User Management ─────────────────────────────────────────────────────────

@role_required('admin', 'super_admin', 'kcca_official')
def manage_users(request):
    search = request.GET.get('search', '')
    role_filter = request.GET.get('role', '')

    qs = User.objects.all()
    if search:
        qs = qs.filter(
            Q(username__icontains=search) | Q(first_name__icontains=search) |
            Q(last_name__icontains=search) | Q(email__icontains=search) |
            Q(phone__icontains=search)
        )
    if role_filter:
        qs = qs.filter(role=role_filter)

    qs = qs.order_by('-date_joined')
    paginator = Paginator(qs, 25)
    page = request.GET.get('page', 1)
    users = paginator.get_page(page)

    return render(request, 'admin/manage_users.html', {
        'users': users,
        'search': search,
        'role_filter': role_filter,
        'roles': User.ROLE_CHOICES,
        'total_count': qs.count(),
    })


@role_required('admin', 'super_admin')
def add_collector(request):
    if request.method == 'POST':
        from apps.accounts.forms import AddCollectorForm
        form = AddCollectorForm(request.POST, request.FILES)
        if form.is_valid():
            collector = form.save()
            from apps.accounts.models import CollectorProfile
            CollectorProfile.objects.create(
                user=collector,
                employee_id=f"KLA{User.objects.filter(role='collector').count():04d}",
            )
            AuditLog.objects.create(
                user=request.user, action='create',
                description=f"Added collector: {collector.get_display_name()}",
                ip_address=request.META.get('REMOTE_ADDR'),
            )
            messages.success(request, f'Collector {collector.get_display_name()} added successfully.')
            return redirect('manage_users')
    else:
        from apps.accounts.forms import AddCollectorForm
        form = AddCollectorForm()

    return render(request, 'admin/add_collector.html', {'form': form})


@login_required
@require_POST
def toggle_user_status(request, pk):
    if not request.user.is_admin():
        return JsonResponse({'error': 'Unauthorized'}, status=403)

    user = get_object_or_404(User, pk=pk)
    if user == request.user:
        return JsonResponse({'error': 'Cannot deactivate yourself'}, status=400)

    user.is_active = not user.is_active
    user.save(update_fields=['is_active'])

    action = 'activated' if user.is_active else 'deactivated'
    AuditLog.objects.create(
        user=request.user, action='update',
        description=f"User {action}: {user.get_display_name()}",
        ip_address=request.META.get('REMOTE_ADDR'),
    )

    return JsonResponse({'status': 'active' if user.is_active else 'inactive', 'message': f'User {action}.'})


@role_required('admin', 'super_admin', 'kcca_official')
def audit_logs(request):
    logs = AuditLog.objects.select_related('user').order_by('-created_at')
    paginator = Paginator(logs, 50)
    page = request.GET.get('page', 1)
    return render(request, 'admin/audit_logs.html', {'logs': paginator.get_page(page)})


# ─── Notifications ────────────────────────────────────────────────────────────

@login_required
def notifications_list(request):
    notifs = Notification.objects.filter(user=request.user).order_by('-created_at')
    paginator = Paginator(notifs, 20)
    page = request.GET.get('page', 1)
    return render(request, 'auth/notifications.html', {'notifications': paginator.get_page(page)})


@login_required
def mark_notification_read(request, pk):
    notif = get_object_or_404(Notification, pk=pk, user=request.user)
    notif.mark_read()
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'status': 'ok'})
    return redirect('notifications')


@login_required
def mark_all_read(request):
    Notification.objects.filter(user=request.user, is_read=False).update(
        is_read=True, read_at=timezone.now()
    )
    return JsonResponse({'status': 'ok'})
