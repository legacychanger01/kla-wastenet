"""
KLA WasteNet Pro — Core Middleware
Audit logging, request timing, security headers
"""
import time
import logging
from django.utils import timezone

logger = logging.getLogger('apps.core')


class AuditLogMiddleware:
    """Log important user actions for security auditing"""

    TRACKED_PATHS = ['/payments/', '/admin-panel/', '/api/']

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        if request.user.is_authenticated and request.method == 'POST':
            for path in self.TRACKED_PATHS:
                if request.path.startswith(path):
                    self._log_action(request, response)
                    break

        return response

    def _log_action(self, request, response):
        try:
            from apps.accounts.models import AuditLog
            AuditLog.objects.create(
                user=request.user,
                action='create',
                description=f"POST {request.path} → {response.status_code}",
                ip_address=self._get_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
            )
        except Exception as e:
            logger.warning(f"AuditLog failed: {e}")

    def _get_ip(self, request):
        x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded:
            return x_forwarded.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')


class RequestTimingMiddleware:
    """Track request processing time"""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start = time.monotonic()
        response = self.get_response(request)
        duration = (time.monotonic() - start) * 1000

        response['X-Response-Time'] = f"{duration:.0f}ms"

        if duration > 1000:
            logger.warning(f"Slow request: {request.method} {request.path} took {duration:.0f}ms")

        return response
