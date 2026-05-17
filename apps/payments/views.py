"""KLA WasteNet Pro — Payment Views"""
import json
import logging
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Sum
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from apps.payments.models import Payment, Invoice
from apps.accounts.models import User, Subscription
from apps.accounts.views import role_required

logger = logging.getLogger('apps.payments')


@login_required
def payment_dashboard(request):
    """Resident payment dashboard"""
    from apps.waste.models import PickupRequest

    payments = Payment.objects.filter(user=request.user).order_by('-created_at')
    paginator = Paginator(payments, 10)
    page = request.GET.get('page', 1)

    unpaid_requests = PickupRequest.objects.filter(
        user=request.user, is_paid=False
    ).exclude(status='cancelled')

    total_paid = Payment.objects.filter(
        user=request.user, status='successful'
    ).aggregate(total=Sum('amount'))['total'] or 0

    active_sub = Subscription.objects.filter(user=request.user, status='active').first()

    return render(request, 'payments/dashboard.html', {
        'payments': paginator.get_page(page),
        'unpaid_requests': unpaid_requests,
        'total_paid': total_paid,
        'active_sub': active_sub,
        'GATEWAYS': Payment.GATEWAY_CHOICES,
    })


@login_required
def initiate_payment(request):
    """Initiate a new payment"""
    from apps.waste.models import PickupRequest

    if request.method == 'GET':
        pending = PickupRequest.objects.filter(
            user=request.user, is_paid=False
        ).exclude(status='cancelled').select_related('category')
        return render(request, 'payments/initiate.html', {
            'pending_requests': pending,
            'GATEWAYS': [
                ('mtn_momo', 'MTN Mobile Money', 'bi-phone', '#FFCC00'),
                ('airtel_money', 'Airtel Money', 'bi-phone-fill', '#FF0000'),
                ('flutterwave', 'Flutterwave (Card/Bank)', 'bi-credit-card', '#F5A623'),
            ],
            'base_fee': settings.WASTE_PICKUP_BASE_FEE,
            'subscription_plans': [
                {'key': 'monthly', 'label': 'Monthly', 'price': settings.SUBSCRIPTION_MONTHLY_FEE, 'pickups': 4},
                {'key': 'quarterly', 'label': 'Quarterly', 'price': settings.SUBSCRIPTION_QUARTERLY_FEE, 'pickups': 12},
                {'key': 'annual', 'label': 'Annual', 'price': settings.SUBSCRIPTION_ANNUAL_FEE, 'pickups': 52},
            ],
        })

    # POST — process payment
    gateway = request.POST.get('gateway', '').strip()
    amount = request.POST.get('amount', '').strip()
    phone = request.POST.get('phone', request.user.phone).strip()
    payment_type = request.POST.get('payment_type', 'pickup')

    if not gateway or not amount:
        messages.error(request, 'Please select a payment method and amount.')
        return redirect('initiate_payment')

    try:
        amount = float(amount)
        if amount <= 0:
            raise ValueError
    except (ValueError, TypeError):
        messages.error(request, 'Invalid amount entered.')
        return redirect('initiate_payment')

    # Create pending payment record
    payment = Payment.objects.create(
        user=request.user,
        gateway=gateway,
        payment_type=payment_type,
        amount=amount,
        phone_number=phone,
        status='pending',
        description=f"{payment_type.replace('_', ' ').title()} payment via {gateway}",
    )

    # Initiate with gateway
    try:
        from apps.payments.services.gateway import get_payment_service
        svc = get_payment_service()

        redirect_url = request.build_absolute_uri(f'/payments/verify/{payment.reference}/')
        result = svc.initiate(
            gateway=gateway,
            user=request.user,
            amount=amount,
            phone=phone,
            reference=payment.reference,
            redirect_url=redirect_url,
        )

        payment.gateway_reference = result.get('reference_id', '')
        payment.gateway_response = result
        payment.status = 'processing'
        payment.save(update_fields=['gateway_reference', 'gateway_response', 'status'])

        # Flutterwave returns a payment link
        if gateway == 'flutterwave' and result.get('payment_link'):
            return redirect(result['payment_link'])

        # MTN/Airtel: show pending screen
        messages.info(request, f'Payment initiated! Please approve on your {gateway.replace("_", " ").title()} prompt.')
        return render(request, 'payments/pending.html', {
            'payment': payment,
            'result': result,
        })

    except Exception as e:
        logger.error(f"Payment initiation error: {e}")
        payment.status = 'failed'
        payment.save(update_fields=['status'])
        messages.error(request, f'Payment initiation failed: {str(e)}')
        return redirect('initiate_payment')


@login_required
def verify_payment_view(request, reference):
    """Poll/verify payment status"""
    payment = get_object_or_404(Payment, reference=reference, user=request.user)

    if payment.status == 'successful':
        return redirect('payment_receipt', reference=reference)

    if request.method == 'POST' or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        # Verify with gateway
        try:
            from apps.payments.services.gateway import get_payment_service
            svc = get_payment_service()
            result = svc.verify(payment.gateway, payment.gateway_reference or payment.reference)
            gateway_status = result.get('status', 'pending')

            if gateway_status == 'successful':
                payment.status = 'successful'
                payment.verified = True
                payment.verified_at = timezone.now()
                payment.completed_at = timezone.now()
                payment.verification_response = result
                payment.save()

                # Mark requests as paid
                from apps.waste.models import PickupRequest
                PickupRequest.objects.filter(
                    user=request.user, is_paid=False
                ).exclude(status='cancelled').update(
                    is_paid=True, payment=payment
                )

                # Create invoice
                _create_invoice(payment)

                # Notify
                try:
                    from apps.notifications.services.notifier import notification_service
                    notification_service.payment_confirmed(payment)
                except Exception:
                    pass

                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'status': 'successful', 'redirect': f'/payments/receipt/{reference}/'})
                return redirect('payment_receipt', reference=reference)

            elif gateway_status == 'failed':
                payment.status = 'failed'
                payment.save(update_fields=['status'])

        except Exception as e:
            logger.error(f"Payment verify error: {e}")

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'status': payment.status})

    return render(request, 'payments/pending.html', {'payment': payment})


def _create_invoice(payment):
    """Auto-create invoice for successful payment"""
    try:
        Invoice.objects.create(
            user=payment.user,
            payment=payment,
            status='paid',
            amount=payment.amount,
            total_amount=payment.amount,
            paid_at=timezone.now(),
            line_items=[
                {
                    'description': payment.description or 'Waste Management Service',
                    'quantity': 1,
                    'unit_price': float(payment.amount),
                    'total': float(payment.amount),
                }
            ],
        )
    except Exception as e:
        logger.warning(f"Invoice creation failed: {e}")


@login_required
def payment_receipt(request, reference):
    payment = get_object_or_404(Payment, reference=reference, user=request.user)
    invoice = getattr(payment, 'invoice', None)
    return render(request, 'payments/receipt.html', {
        'payment': payment,
        'invoice': invoice,
    })


@login_required
def subscription_plans(request):
    """Manage subscription plans"""
    active_sub = Subscription.objects.filter(user=request.user, status='active').first()
    past_subs = Subscription.objects.filter(user=request.user).order_by('-created_at')[:5]

    plans = [
        {
            'key': 'free',
            'label': 'Free',
            'price': 0,
            'period': '',
            'features': ['Pay per pickup', 'Basic support', 'Email notifications'],
            'recommended': False,
        },
        {
            'key': 'monthly',
            'label': 'Monthly',
            'price': settings.SUBSCRIPTION_MONTHLY_FEE,
            'period': '/month',
            'features': ['4 pickups/month', 'Priority support', 'SMS + Email', 'Recycling rewards'],
            'recommended': False,
        },
        {
            'key': 'quarterly',
            'label': 'Quarterly',
            'price': settings.SUBSCRIPTION_QUARTERLY_FEE,
            'period': '/quarter',
            'features': ['12 pickups/quarter', 'Priority support', 'All notifications', 'Recycling rewards', '10% discount'],
            'recommended': True,
        },
        {
            'key': 'annual',
            'label': 'Annual',
            'price': settings.SUBSCRIPTION_ANNUAL_FEE,
            'period': '/year',
            'features': ['52 pickups/year', 'VIP support', 'All features', 'Recycling rewards', '20% discount', 'Carbon tracking'],
            'recommended': False,
        },
    ]

    return render(request, 'payments/subscription.html', {
        'plans': plans,
        'active_sub': active_sub,
        'past_subs': past_subs,
    })


# ─── Admin Payment Dashboard ──────────────────────────────────────────────────

@role_required('admin', 'super_admin', 'kcca_official')
def admin_payments(request):
    from django.db.models.functions import TruncMonth

    payments = Payment.objects.select_related('user').order_by('-created_at')

    # Filters
    gateway_filter = request.GET.get('gateway', '')
    status_filter = request.GET.get('status', '')
    if gateway_filter:
        payments = payments.filter(gateway=gateway_filter)
    if status_filter:
        payments = payments.filter(status=status_filter)

    # Stats
    stats = {
        'total_revenue': Payment.objects.filter(status='successful').aggregate(t=Sum('amount'))['t'] or 0,
        'this_month': Payment.objects.filter(
            status='successful',
            created_at__month=timezone.now().month
        ).aggregate(t=Sum('amount'))['t'] or 0,
        'total_transactions': Payment.objects.filter(status='successful').count(),
        'pending': Payment.objects.filter(status__in=('pending', 'processing')).count(),
    }

    # Revenue by gateway
    by_gateway = list(
        Payment.objects.filter(status='successful')
        .values('gateway')
        .annotate(total=Sum('amount'), count=Count('id'))
        .order_by('-total')
    )

    # Monthly trend
    monthly = list(
        Payment.objects.filter(status='successful')
        .annotate(month=TruncMonth('created_at'))
        .values('month')
        .annotate(total=Sum('amount'), count=Count('id'))
        .order_by('month')
    )

    paginator = Paginator(payments, 20)
    page = request.GET.get('page', 1)

    return render(request, 'admin/payments.html', {
        'payments': paginator.get_page(page),
        'stats': stats,
        'by_gateway': by_gateway,
        'monthly': monthly,
        'GATEWAYS': Payment.GATEWAY_CHOICES,
        'STATUS_CHOICES': Payment.STATUS_CHOICES,
        'gateway_filter': gateway_filter,
        'status_filter': status_filter,
    })


# ─── Webhook Handlers ─────────────────────────────────────────────────────────

@csrf_exempt
def mtn_webhook(request):
    """MTN Mobile Money webhook"""
    if request.method == 'POST':
        try:
            from apps.payments.models import PaymentWebhook
            data = json.loads(request.body)
            PaymentWebhook.objects.create(
                gateway='mtn_momo',
                event_type=data.get('type', 'unknown'),
                payload=data,
                headers=dict(request.headers),
            )
        except Exception as e:
            logger.error(f"MTN webhook error: {e}")
        return HttpResponse(status=200)
    return HttpResponse(status=405)


@csrf_exempt
def flutterwave_webhook(request):
    """Flutterwave webhook"""
    if request.method == 'POST':
        try:
            signature = request.headers.get('verif-hash', '')
            body = request.body.decode()
            data = json.loads(body)

            from apps.payments.models import PaymentWebhook
            PaymentWebhook.objects.create(
                gateway='flutterwave',
                event_type=data.get('event', 'unknown'),
                payload=data,
                headers=dict(request.headers),
            )

            # Process immediately for successful payments
            if data.get('event') == 'charge.completed' and data.get('data', {}).get('status') == 'successful':
                tx_ref = data['data'].get('tx_ref')
                payment = Payment.objects.filter(reference=tx_ref, status='processing').first()
                if payment:
                    payment.status = 'successful'
                    payment.verified = True
                    payment.verified_at = timezone.now()
                    payment.completed_at = timezone.now()
                    payment.gateway_response = data
                    payment.save()
                    _create_invoice(payment)

        except Exception as e:
            logger.error(f"FLW webhook error: {e}")
        return HttpResponse(status=200)
    return HttpResponse(status=405)
