"""
KLA WasteNet Pro — Notifications Service
SMS (Twilio, Africa's Talking), Email, Firebase Push Notifications
"""
import logging
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags

logger = logging.getLogger('apps.notifications')


class SMSService:
    """SMS via Africa's Talking (primary) with Twilio fallback"""

    def send_africastalking(self, phone, message):
        try:
            import africastalking
            africastalking.initialize(settings.AT_USERNAME, settings.AT_API_KEY)
            sms = africastalking.SMS
            response = sms.send(message, [phone], sender_id=settings.AT_SENDER_ID)
            logger.info(f"AT SMS sent to {phone}: {response}")
            return True, response
        except Exception as e:
            logger.error(f"AT SMS failed: {str(e)}")
            return False, str(e)

    def send_twilio(self, phone, message):
        try:
            from twilio.rest import Client
            client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
            msg = client.messages.create(
                body=message,
                from_=settings.TWILIO_PHONE_NUMBER,
                to=phone,
            )
            logger.info(f"Twilio SMS sent to {phone}: {msg.sid}")
            return True, msg.sid
        except Exception as e:
            logger.error(f"Twilio SMS failed: {str(e)}")
            return False, str(e)

    def send(self, phone, message):
        """Send SMS with AT primary, Twilio fallback"""
        if settings.AT_API_KEY:
            success, resp = self.send_africastalking(phone, message)
            if success:
                return True
        if settings.TWILIO_ACCOUNT_SID:
            success, _ = self.send_twilio(phone, message)
            return success
        logger.warning("No SMS provider configured. Message not sent.")
        return False


class EmailService:
    """Transactional email notifications"""

    def send(self, user, subject, template_name, context):
        try:
            context['user'] = user
            context['site_url'] = settings.SITE_URL
            html = render_to_string(f"emails/{template_name}.html", context)
            plain = strip_tags(html)
            send_mail(
                subject=f"[KLA WasteNet] {subject}",
                message=plain,
                html_message=html,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=False,
            )
            logger.info(f"Email sent: {subject} → {user.email}")
            return True
        except Exception as e:
            logger.error(f"Email send failed: {str(e)}")
            return False


class PushNotificationService:
    """Firebase Cloud Messaging push notifications"""

    def send(self, user, title, body, data=None):
        if not user.fcm_token or not settings.FIREBASE_CREDENTIALS_PATH:
            return False

        try:
            import firebase_admin
            from firebase_admin import messaging

            if not firebase_admin._apps:
                cred = firebase_admin.credentials.Certificate(settings.FIREBASE_CREDENTIALS_PATH)
                firebase_admin.initialize_app(cred)

            msg = messaging.Message(
                notification=messaging.Notification(title=title, body=body),
                data=data or {},
                token=user.fcm_token,
                android=messaging.AndroidConfig(priority='high'),
                apns=messaging.APNSConfig(
                    payload=messaging.APNSPayload(
                        aps=messaging.Aps(sound='default')
                    )
                ),
            )
            resp = messaging.send(msg)
            logger.info(f"Push sent: {resp}")
            return True
        except Exception as e:
            logger.error(f"Push notification failed: {str(e)}")
            return False


class NotificationOrchestrator:
    """
    Central notification orchestrator.
    Sends appropriate notifications based on user preferences and event type.
    """

    def __init__(self):
        self.sms = SMSService()
        self.email = EmailService()
        self.push = PushNotificationService()

    def _get_channels(self, user):
        return {
            'sms': user.sms_notifications and bool(user.phone),
            'email': user.email_notifications and bool(user.email),
            'push': user.push_notifications and bool(user.fcm_token),
        }

    def pickup_submitted(self, pickup_request):
        user = pickup_request.user
        channels = self._get_channels(user)
        msg = (
            f"Your waste pickup request #{pickup_request.request_number} has been submitted. "
            f"We'll assign a collector soon. — KLA WasteNet"
        )
        if channels['sms']:
            self.sms.send(user.phone, msg)
        if channels['email']:
            self.email.send(user, "Pickup Request Submitted", "pickup_submitted", {
                "pickup": pickup_request
            })
        if channels['push']:
            self.push.send(user, "Request Submitted ✅", msg)

    def pickup_assigned(self, assignment):
        user = assignment.pickup_request.user
        collector = assignment.collector
        channels = self._get_channels(user)
        date = assignment.scheduled_date.strftime('%d %b %Y') if assignment.scheduled_date else 'soon'
        msg = (
            f"Your request #{assignment.pickup_request.request_number} has been assigned to "
            f"{collector.get_display_name()} scheduled for {date}. — KLA WasteNet"
        )
        if channels['sms']:
            self.sms.send(user.phone, msg)
        if channels['email']:
            self.email.send(user, "Collector Assigned", "pickup_assigned", {
                "assignment": assignment, "collector": collector
            })
        if channels['push']:
            self.push.send(user, "Collector Assigned 🚛", msg)

    def pickup_completed(self, pickup_request):
        user = pickup_request.user
        channels = self._get_channels(user)
        msg = (
            f"Pickup #{pickup_request.request_number} completed! "
            f"Please rate your experience. Thank you — KLA WasteNet"
        )
        if channels['sms']:
            self.sms.send(user.phone, msg)
        if channels['email']:
            self.email.send(user, "Pickup Completed", "pickup_completed", {
                "pickup": pickup_request
            })
        if channels['push']:
            self.push.send(user, "Pickup Complete ♻️", msg)

    def payment_confirmed(self, payment):
        user = payment.user
        channels = self._get_channels(user)
        msg = (
            f"Payment of UGX {payment.amount:,.0f} confirmed! "
            f"Ref: {payment.reference} — KLA WasteNet"
        )
        if channels['sms']:
            self.sms.send(user.phone, msg)
        if channels['email']:
            self.email.send(user, "Payment Confirmed", "payment_confirmed", {
                "payment": payment
            })
        if channels['push']:
            self.push.send(user, "Payment Confirmed 💳", msg)

    def collector_new_assignment(self, assignment):
        collector = assignment.collector
        if not collector:
            return
        channels = self._get_channels(collector)
        pickup = assignment.pickup_request
        date = assignment.scheduled_date.strftime('%d %b %Y') if assignment.scheduled_date else 'today'
        msg = (
            f"New assignment! Pickup #{pickup.request_number} at {pickup.address} "
            f"scheduled for {date}. — KLA WasteNet"
        )
        if channels['sms']:
            self.sms.send(collector.phone, msg)
        if channels['push']:
            self.push.send(collector, "New Assignment 📍", msg)

    def subscription_expiring(self, user, days_remaining):
        channels = self._get_channels(user)
        msg = (
            f"Your KLA WasteNet subscription expires in {days_remaining} days. "
            f"Renew now at {settings.SITE_URL}/payments/subscription/ — KLA WasteNet"
        )
        if channels['sms']:
            self.sms.send(user.phone, msg)
        if channels['email']:
            self.email.send(user, "Subscription Expiring Soon", "subscription_expiring", {
                "days_remaining": days_remaining
            })

    def smart_bin_full(self, smart_bin):
        """Alert admin and nearby collectors when a smart bin is nearly full"""
        from apps.accounts.models import User
        admins = User.objects.filter(role__in=['admin', 'super_admin', 'kcca_official'])
        msg = (
            f"⚠️ Smart Bin {smart_bin.bin_id} at {smart_bin.location_name} is "
            f"{smart_bin.fill_level}% full. Immediate collection needed! — KLA WasteNet"
        )
        for admin in admins:
            if admin.push_notifications and admin.fcm_token:
                self.push.send(admin, "Smart Bin Alert ⚠️", msg)


# Singleton
notification_service = NotificationOrchestrator()
