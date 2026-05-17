"""
KLA WasteNet Pro — Waste API Serializers
"""
from rest_framework import serializers
from apps.waste.models import (
    WasteCategory, PickupRequest, Assignment,
    CollectionRoute, CollectorLocationUpdate, SmartBin, WasteReport
)
from apps.accounts.models import User


class WasteCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = WasteCategory
        fields = ['id', 'name', 'slug', 'description', 'icon', 'color',
                  'base_fee', 'is_hazardous', 'is_recyclable', 'is_active']


class PickupRequestListSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    category_icon = serializers.CharField(source='category.icon', read_only=True)
    user_name = serializers.CharField(source='user.get_display_name', read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)

    class Meta:
        model = PickupRequest
        fields = [
            'id', 'request_number', 'user', 'user_name', 'category', 'category_name',
            'category_icon', 'status', 'priority', 'division', 'address',
            'preferred_date', 'amount_due', 'is_paid', 'is_overdue',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['request_number', 'is_paid', 'amount_due']


class PickupRequestDetailSerializer(serializers.ModelSerializer):
    category = WasteCategorySerializer(read_only=True)
    category_id = serializers.UUIDField(write_only=True)

    class Meta:
        model = PickupRequest
        fields = [
            'id', 'request_number', 'user', 'category', 'category_id',
            'status', 'priority', 'division', 'address', 'latitude', 'longitude',
            'location_instructions', 'estimated_weight_kg', 'waste_description',
            'waste_image', 'quantity', 'preferred_date', 'preferred_time_start',
            'preferred_time_end', 'amount_due', 'is_paid', 'resident_rating',
            'resident_feedback', 'notes', 'created_at', 'collected_at',
        ]
        read_only_fields = ['request_number', 'user', 'is_paid', 'amount_due',
                            'resident_rating', 'resident_feedback', 'collected_at']

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)


class AssignmentSerializer(serializers.ModelSerializer):
    collector_name = serializers.CharField(source='collector.get_display_name', read_only=True)
    collector_phone = serializers.CharField(source='collector.phone', read_only=True)
    collector_latitude = serializers.DecimalField(
        source='collector.latitude', max_digits=9, decimal_places=6, read_only=True
    )
    collector_longitude = serializers.DecimalField(
        source='collector.longitude', max_digits=9, decimal_places=6, read_only=True
    )

    class Meta:
        model = Assignment
        fields = [
            'id', 'pickup_request', 'collector', 'collector_name', 'collector_phone',
            'collector_latitude', 'collector_longitude', 'scheduled_date',
            'scheduled_time_start', 'estimated_arrival', 'actual_arrival',
            'collector_notes', 'assigned_at', 'completed_at',
        ]


class CollectorLocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = CollectorLocationUpdate
        fields = ['id', 'collector', 'latitude', 'longitude', 'speed_kmh',
                  'heading', 'accuracy_meters', 'timestamp']
        read_only_fields = ['collector']

    def create(self, validated_data):
        validated_data['collector'] = self.context['request'].user
        # Also update user's main location
        user = validated_data['collector']
        user.update_location(validated_data['latitude'], validated_data['longitude'])
        return super().create(validated_data)


class SmartBinSerializer(serializers.ModelSerializer):
    needs_collection = serializers.BooleanField(read_only=True)

    class Meta:
        model = SmartBin
        fields = ['id', 'bin_id', 'location_name', 'division', 'latitude', 'longitude',
                  'capacity_liters', 'fill_level', 'status', 'last_emptied',
                  'needs_collection', 'sensor_data']


class WasteReportSerializer(serializers.ModelSerializer):
    reporter_name = serializers.CharField(source='reporter.get_display_name', read_only=True)

    class Meta:
        model = WasteReport
        fields = [
            'id', 'reporter', 'reporter_name', 'issue_type', 'title', 'description',
            'division', 'address', 'latitude', 'longitude', 'image',
            'status', 'created_at',
        ]
        read_only_fields = ['reporter', 'status']

    def create(self, validated_data):
        validated_data['reporter'] = self.context['request'].user
        return super().create(validated_data)
