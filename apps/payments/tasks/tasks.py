"""
KLA WasteNet Pro — Payment Celery Tasks
"""
import logging
from celery import shared_task
from django.utils import timezone

logger = logging.getLogger('apps.payments.tasks')


@shared_task(bind=True, max_retries=5, default_retry_delay=120)
def verify_pending_payments(self):
    """Poll gateway APIs to verify processing payments"""
    try:
        from apps.payments.models import Payment
        from apps.payments.services.gateway import get_payment_service

        cutoff = timezone.now() - timezone.timedelta(hours=2)
        pending = Payment.objects.filter(
            status='processing',
            created_at__gte=cutoff,
        ).select_related('user')

        svc = get_payment_service()
        verified = 0
        failed = 0

        for payment in pending:
            try:
                ref = payment.gateway_reference or payment.reference
                result = svc.verify(payment.gateway, ref)
                gateway_status = result.get('status', 'pending')

                if gateway_status == 'successful':
                    payment.status = 'successful'
                    payment.verified = True
                    payment.verified_at = timezone.now()
                    payment.completed_at = timezone.now()
                    payment.verification_response = result
                    payment.save()

                    # Mark pickup requests as paid
                    from apps.waste.models import PickupRequest
                    PickupRequest.objects.filter(
                        user=payment.user, is_paid=False
                    ).exclude(status='cancelled').update(
                        is_paid=True, payment=payment
                    )

                    # Create invoice
                    _create_invoice_for_payment(payment)

                    # Notify user
                    try:
                        from apps.notifications.services.notifier import notification_service
                        notification_service.payment_confirmed(payment)
                    except Exception:
                        pass

                    verified += 1

                elif gateway_status == 'failed':
                    payment.status = 'failed'
                    payment.save(update_fields=['status'])
                    failed += 1

            except Exception as e:
                logger.warning(f"Payment verify error [{payment.reference}]: {e}")

        logger.info(f"Payment verification: {verified} confirmed, {failed} failed")
        return {'verified': verified, 'failed': failed}

    except Exception as exc:
        logger.error(f"verify_pending_payments task failed: {exc}")
        raise self.retry(exc=exc)


def _create_invoice_for_payment(payment):
    """Create invoice record for a successful payment"""
    try:
        from apps.payments.models import Invoice
        if not hasattr(payment, 'invoice'):
            Invoice.objects.create(
                user=payment.user,
                payment=payment,
                status='paid',
                amount=payment.amount,
                total_amount=payment.amount,
                paid_at=timezone.now(),
                line_items=[{
                    'description': payment.description or 'Waste Management Service',
                    'quantity': 1,
                    'unit_price': float(payment.amount),
                    'total': float(payment.amount),
                }],
            )
    except Exception as e:
        logger.warning(f"Invoice creation failed: {e}")


@shared_task
def process_webhook(webhook_id):
    """Process a stored webhook payload asynchronously"""
    try:
        from apps.payments.models import PaymentWebhook, Payment

        webhook = PaymentWebhook.objects.get(pk=webhook_id)
        if webhook.processed:
            return

        payload = webhook.payload
        gateway = webhook.gateway

        if gateway == 'flutterwave':
            if payload.get('event') == 'charge.completed':
                tx_data = payload.get('data', {})
                if tx_data.get('status') == 'successful':
                    tx_ref = tx_data.get('tx_ref')
                    payment = Payment.objects.filter(
                        reference=tx_ref, status='processing'
                    ).first()
                    if payment:
                        payment.status = 'successful'
                        payment.verified = True
                        payment.verified_at = timezone.now()
                        payment.completed_at = timezone.now()
                        payment.save()
                        _create_invoice_for_payment(payment)
                        webhook.payment = payment

        elif gateway == 'mtn_momo':
            ref_id = payload.get('referenceId', '')
            payment = Payment.objects.filter(
                gateway_reference=ref_id, status='processing'
            ).first()
            if payment and payload.get('status') == 'SUCCESSFUL':
                payment.status = 'successful'
                payment.verified = True
                payment.verified_at = timezone.now()
                payment.completed_at = timezone.now()
                payment.save()
                _create_invoice_for_payment(payment)
                webhook.payment = payment

        webhook.processed = True
        webhook.processed_at = timezone.now()
        webhook.save()

    except Exception as e:
        logger.error(f"process_webhook failed [{webhook_id}]: {e}")
        try:
            from apps.payments.models import PaymentWebhook
            PaymentWebhook.objects.filter(pk=webhook_id).update(error=str(e))
        except Exception:
            pass
        raise
