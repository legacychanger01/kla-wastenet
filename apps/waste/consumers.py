"""
KLA WasteNet Pro — WebSocket Consumers
Real-time collector tracking via Django Channels
"""
import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer

logger = logging.getLogger('apps.waste.consumers')


class CollectorTrackingConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time collector GPS tracking.
    Residents connect to track their assigned collector.
    Admins can track all collectors.
    """

    async def connect(self):
        self.user = self.scope.get('user')

        if not self.user or not self.user.is_authenticated:
            await self.close(code=4001)
            return

        self.collector_id = self.scope['url_route']['kwargs'].get('collector_id')

        if self.collector_id:
            self.group_name = f'tracker_{self.collector_id}'
        else:
            # Admins can join the city-wide group
            if not (self.user.is_admin() if hasattr(self.user, 'is_admin') else False):
                await self.close(code=4003)
                return
            self.group_name = 'tracker_all'

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        logger.info(f"WS connected: {self.user} → group {self.group_name}")

        await self.send(text_data=json.dumps({
            'type': 'connected',
            'message': 'Tracking started',
            'group': self.group_name,
        }))

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
        logger.info(f"WS disconnected: code={close_code}")

    async def receive(self, text_data):
        """Handle incoming messages (ping/pong keepalive)"""
        try:
            data = json.loads(text_data)
            if data.get('type') == 'ping':
                await self.send(text_data=json.dumps({'type': 'pong'}))
        except json.JSONDecodeError:
            pass

    async def location_update(self, event):
        """Broadcast location update to connected clients"""
        await self.send(text_data=json.dumps({
            'type': 'location_update',
            'collector_id': event['collector_id'],
            'latitude': event['latitude'],
            'longitude': event['longitude'],
            'timestamp': event.get('timestamp', ''),
            'speed_kmh': event.get('speed_kmh'),
        }))


class NotificationConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time in-app notifications.
    Each authenticated user gets their own channel.
    """

    async def connect(self):
        self.user = self.scope.get('user')

        if not self.user or not self.user.is_authenticated:
            await self.close(code=4001)
            return

        self.group_name = f'notifications_{self.user.id}'
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        # Send unread count on connect
        try:
            from apps.notifications.models import Notification
            from asgiref.sync import sync_to_async

            @sync_to_async
            def get_unread():
                return Notification.objects.filter(
                    user=self.user, is_read=False
                ).count()

            unread = await get_unread()
            await self.send(text_data=json.dumps({
                'type': 'unread_count',
                'count': unread,
            }))
        except Exception as e:
            logger.warning(f"Unread count error: {e}")

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            if data.get('type') == 'mark_read':
                notif_id = data.get('notification_id')
                if notif_id:
                    from apps.notifications.models import Notification
                    from asgiref.sync import sync_to_async

                    @sync_to_async
                    def mark():
                        try:
                            n = Notification.objects.get(pk=notif_id, user=self.user)
                            n.mark_read()
                        except Notification.DoesNotExist:
                            pass

                    await mark()
        except json.JSONDecodeError:
            pass

    async def new_notification(self, event):
        """Push new notification to connected user"""
        await self.send(text_data=json.dumps({
            'type': 'new_notification',
            'title': event.get('title'),
            'message': event.get('message'),
            'notification_type': event.get('notification_type'),
            'action_url': event.get('action_url', ''),
        }))

    async def unread_count_update(self, event):
        """Update unread notification badge"""
        await self.send(text_data=json.dumps({
            'type': 'unread_count',
            'count': event.get('count', 0),
        }))
