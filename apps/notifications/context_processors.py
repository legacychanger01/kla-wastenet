"""Notification count context processor"""


def unread_notifications(request):
    if not request.user.is_authenticated:
        return {'unread_notifications_count': 0}
    try:
        from apps.notifications.models import Notification
        count = Notification.objects.filter(user=request.user, is_read=False).count()
        return {'unread_notifications_count': count}
    except Exception:
        return {'unread_notifications_count': 0}
