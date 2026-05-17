"""
KLA WasteNet Pro — Waste API ViewSets
Full REST API for mobile app integration
"""
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from django.db.models import Q

from apps.waste.models import (
    WasteCategory, PickupRequest, Assignment,
    CollectorLocationUpdate, SmartBin, WasteReport
)
from apps.waste.api.serializers import (
    WasteCategorySerializer, PickupRequestListSerializer,
    PickupRequestDetailSerializer, AssignmentSerializer,
    CollectorLocationSerializer, SmartBinSerializer, WasteReportSerializer
)


class IsAdminOrReadOwn(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.user.is_admin():
            return True
        if hasattr(obj, 'user'):
            return obj.user == request.user
        return False


class WasteCategoryViewSet(viewsets.ReadOnlyModelViewSet):
    """List all waste categories"""
    queryset = WasteCategory.objects.filter(is_active=True)
    serializer_class = WasteCategorySerializer
    permission_classes = [permissions.IsAuthenticated]


class PickupRequestViewSet(viewsets.ModelViewSet):
    """
    CRUD for pickup requests.
    Residents see only their own; admins see all.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        qs = PickupRequest.objects.select_related('user', 'category', 'assignment__collector')

        if user.is_resident():
            qs = qs.filter(user=user)
        elif user.is_collector():
            qs = qs.filter(assignment__collector=user)
        elif not user.is_admin():
            qs = qs.none()

        # Filtering
        status_filter = self.request.query_params.get('status')
        division_filter = self.request.query_params.get('division')
        if status_filter:
            qs = qs.filter(status=status_filter)
        if division_filter:
            qs = qs.filter(division=division_filter)

        return qs.order_by('-created_at')

    def get_serializer_class(self):
        if self.action in ('retrieve', 'create', 'update', 'partial_update'):
            return PickupRequestDetailSerializer
        return PickupRequestListSerializer

    @action(detail=True, methods=['post'])
    def rate(self, request, pk=None):
        """Resident rates a completed pickup"""
        pickup = self.get_object()
        if pickup.user != request.user:
            return Response({'error': 'Not your request'}, status=403)
        if pickup.status != 'collected':
            return Response({'error': 'Can only rate collected pickups'}, status=400)

        rating = request.data.get('rating')
        feedback = request.data.get('feedback', '')

        if not rating or not (1 <= int(rating) <= 5):
            return Response({'error': 'Rating must be 1-5'}, status=400)

        pickup.resident_rating = int(rating)
        pickup.resident_feedback = feedback
        pickup.rated_at = timezone.now()
        pickup.save(update_fields=['resident_rating', 'resident_feedback', 'rated_at'])

        # Update collector average rating
        if hasattr(pickup, 'assignment') and pickup.assignment.collector:
            collector = pickup.assignment.collector
            from django.db.models import Avg
            avg = PickupRequest.objects.filter(
                assignment__collector=collector,
                resident_rating__isnull=False
            ).aggregate(avg=Avg('resident_rating'))['avg']
            if hasattr(collector, 'collector_profile'):
                collector.collector_profile.rating = round(avg, 2)
                collector.collector_profile.save(update_fields=['rating'])

        return Response({'message': 'Rating submitted'})

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def cancel(self, request, pk=None):
        """Cancel a pending pickup request"""
        pickup = self.get_object()
        if pickup.user != request.user:
            return Response({'error': 'Not your request'}, status=403)
        if pickup.status not in ('pending', 'assigned'):
            return Response({'error': 'Cannot cancel request at this stage'}, status=400)

        pickup.status = 'cancelled'
        pickup.cancellation_reason = request.data.get('reason', '')
        pickup.save(update_fields=['status', 'cancellation_reason'])

        return Response({'message': 'Request cancelled'})


class AssignmentViewSet(viewsets.ModelViewSet):
    """Manage pickup assignments"""
    serializer_class = AssignmentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        qs = Assignment.objects.select_related(
            'pickup_request__user', 'pickup_request__category', 'collector'
        )
        if user.is_collector():
            return qs.filter(collector=user)
        elif user.is_admin():
            return qs.all()
        return qs.none()

    @action(detail=True, methods=['post'])
    def update_status(self, request, pk=None):
        """Collector updates pickup status"""
        assignment = self.get_object()
        if assignment.collector != request.user:
            return Response({'error': 'Not your assignment'}, status=403)

        new_status = request.data.get('status')
        valid = ['in_progress', 'collected']
        if new_status not in valid:
            return Response({'error': f'Status must be one of {valid}'}, status=400)

        pickup = assignment.pickup_request
        pickup.status = new_status
        if new_status == 'collected':
            assignment.completed_at = timezone.now()
            pickup.collected_at = timezone.now()
            assignment.weight_collected_kg = request.data.get('weight_kg')
            assignment.collector_notes = request.data.get('notes', '')

            # Update collector stats
            if hasattr(request.user, 'collector_profile'):
                profile = request.user.collector_profile
                profile.total_collections += 1
                profile.save(update_fields=['total_collections'])

        pickup.save()
        assignment.save()

        # Send notification
        try:
            from apps.notifications.services.notifier import notification_service
            if new_status == 'collected':
                notification_service.pickup_completed(pickup)
        except Exception:
            pass

        return Response({'message': f'Status updated to {new_status}'})


class CollectorLocationViewSet(viewsets.ModelViewSet):
    """Real-time GPS location updates from collectors"""
    serializer_class = CollectorLocationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_collector():
            return CollectorLocationUpdate.objects.filter(collector=user).order_by('-timestamp')[:100]
        elif user.is_admin():
            return CollectorLocationUpdate.objects.select_related('collector').order_by('-timestamp')[:500]
        return CollectorLocationUpdate.objects.none()

    @action(detail=False, methods=['get'])
    def live_collectors(self, request):
        """Get current location of all active collectors"""
        if not request.user.is_admin() and not request.user.is_resident():
            return Response({'error': 'Unauthorized'}, status=403)

        from apps.accounts.models import User
        from django.utils import timezone
        from datetime import timedelta

        # Collectors who updated location in last 30 minutes
        recent_cutoff = timezone.now() - timedelta(minutes=30)

        collectors = User.objects.filter(
            role='collector',
            is_active=True,
            location_updated_at__gte=recent_cutoff,
        ).select_related('collector_profile')

        data = [
            {
                'id': str(c.id),
                'name': c.get_display_name(),
                'phone': c.phone,
                'latitude': float(c.latitude) if c.latitude else None,
                'longitude': float(c.longitude) if c.longitude else None,
                'status': c.collector_profile.status if hasattr(c, 'collector_profile') else 'unknown',
                'location_updated': c.location_updated_at,
            }
            for c in collectors if c.latitude and c.longitude
        ]

        return Response(data)


class SmartBinViewSet(viewsets.ReadOnlyModelViewSet):
    """Smart bin monitoring data"""
    queryset = SmartBin.objects.filter(is_active=True)
    serializer_class = SmartBinSerializer
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=['get'])
    def critical(self, request):
        """Bins at ≥80% capacity needing immediate collection"""
        bins = SmartBin.objects.filter(is_active=True, fill_level__gte=80)
        return Response(SmartBinSerializer(bins, many=True).data)


class WasteReportViewSet(viewsets.ModelViewSet):
    """Community waste issue reports"""
    serializer_class = WasteReportSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_admin():
            return WasteReport.objects.all()
        return WasteReport.objects.filter(reporter=user)
