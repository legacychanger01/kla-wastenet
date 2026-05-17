"""
KLA WasteNet Pro — ASGI Configuration
Supports both HTTP (Django) and WebSocket (Channels)
"""
import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from channels.security.websocket import AllowedHostsOriginValidator
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.production')
django.setup()

from django.urls import re_path
from apps.waste.consumers import CollectorTrackingConsumer, NotificationConsumer

websocket_urlpatterns = [
    re_path(r'^ws/track/(?P<collector_id>[0-9a-f-]+)/$', CollectorTrackingConsumer.as_asgi()),
    re_path(r'^ws/track/$', CollectorTrackingConsumer.as_asgi()),
    re_path(r'^ws/notifications/$', NotificationConsumer.as_asgi()),
]

application = ProtocolTypeRouter({
    'http': get_asgi_application(),
    'websocket': AllowedHostsOriginValidator(
        AuthMiddlewareStack(
            URLRouter(websocket_urlpatterns)
        )
    ),
})
