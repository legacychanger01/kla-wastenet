"""
KLA WasteNet Pro — AI Analytics & Predictions Service
Machine learning for demand forecasting, route optimization, and insights
"""
import logging
from datetime import date, timedelta
from django.db.models import Count, Avg, Q
from django.utils import timezone

logger = logging.getLogger('apps.analytics')


class WasteDemandPredictor:
    """
    Predicts waste collection demand using historical data.
    Uses simple but effective statistical models suitable for production.
    """

    def predict_division_demand(self, division, days_ahead=7):
        """
        Predict pickup requests per day for a division over next N days.
        Uses moving average with day-of-week seasonality.
        """
        from apps.waste.models import PickupRequest

        # Get historical data (last 90 days)
        end = date.today()
        start = end - timedelta(days=90)

        daily = (
            PickupRequest.objects
            .filter(division=division, created_at__date__range=[start, end])
            .extra(select={'day': 'DATE(created_at)'})
            .values('day')
            .annotate(count=Count('id'))
            .order_by('day')
        )

        # Build day-of-week average
        dow_counts = {i: [] for i in range(7)}
        for row in daily:
            try:
                d = row['day']
                if hasattr(d, 'weekday'):
                    dow_counts[d.weekday()].append(row['count'])
            except Exception:
                pass

        dow_avg = {}
        for dow, counts in dow_counts.items():
            dow_avg[dow] = round(sum(counts) / len(counts), 1) if counts else 0

        # Generate predictions
        predictions = []
        for i in range(days_ahead):
            future_date = date.today() + timedelta(days=i + 1)
            dow = future_date.weekday()
            avg = dow_avg.get(dow, 0)

            # Simple trend: adjust by 5% weekly growth assumption
            trend_factor = 1 + (0.005 * i)

            predictions.append({
                "date": future_date.isoformat(),
                "day_name": future_date.strftime("%A"),
                "predicted_requests": round(avg * trend_factor, 1),
                "confidence": "high" if len(dow_counts.get(dow, [])) >= 8 else "low",
            })

        return predictions

    def predict_peak_hours(self, division=None):
        """Analyze which hours of the day have most requests"""
        from apps.waste.models import PickupRequest

        qs = PickupRequest.objects.filter(
            created_at__date__gte=date.today() - timedelta(days=30)
        )
        if division:
            qs = qs.filter(division=division)

        hourly = {}
        for req in qs.values_list('created_at', flat=True):
            h = req.hour
            hourly[h] = hourly.get(h, 0) + 1

        return [
            {"hour": h, "label": f"{h:02d}:00", "count": c}
            for h, c in sorted(hourly.items())
        ]

    def identify_hotspots(self):
        """Find divisions with highest waste generation"""
        from apps.waste.models import PickupRequest

        return list(
            PickupRequest.objects
            .filter(created_at__date__gte=date.today() - timedelta(days=30))
            .values('division')
            .annotate(
                total=Count('id'),
                pending=Count('id', filter=Q(status='pending')),
                collected=Count('id', filter=Q(status='collected')),
            )
            .order_by('-total')
        )


class RouteOptimizer:
    """
    Optimizes waste collection routes using nearest-neighbor heuristic.
    For production, can be upgraded to use Google OR-Tools or OpenRouteService.
    """

    def optimize_route(self, assignments):
        """
        Given a list of assignments with lat/lng, return optimized order.
        Uses nearest-neighbor algorithm (greedy).

        Args:
            assignments: QuerySet of Assignment objects

        Returns:
            Ordered list of assignment IDs
        """
        import math

        def haversine(lat1, lon1, lat2, lon2):
            R = 6371  # Earth radius km
            phi1, phi2 = math.radians(lat1), math.radians(lat2)
            dphi = math.radians(lat2 - lat1)
            dlambda = math.radians(lon2 - lon1)
            a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
            return 2*R*math.atan2(math.sqrt(a), math.sqrt(1-a))

        # Filter assignments with valid coordinates
        points = []
        for a in assignments:
            lat = a.pickup_request.latitude
            lng = a.pickup_request.longitude
            if lat and lng:
                points.append({
                    "id": str(a.id),
                    "lat": float(lat),
                    "lng": float(lng),
                    "address": a.pickup_request.address,
                })

        if len(points) <= 1:
            return [p["id"] for p in points]

        # Nearest-neighbor from first point
        ordered = [points[0]]
        remaining = points[1:]

        while remaining:
            last = ordered[-1]
            nearest = min(
                remaining,
                key=lambda p: haversine(last["lat"], last["lng"], p["lat"], p["lng"])
            )
            ordered.append(nearest)
            remaining.remove(nearest)

        return [p["id"] for p in ordered]

    def estimate_route_metrics(self, ordered_assignments):
        """Estimate total distance and time for a route"""
        import math

        def haversine(lat1, lon1, lat2, lon2):
            R = 6371
            phi1, phi2 = math.radians(lat1), math.radians(lat2)
            dphi = math.radians(lat2 - lat1)
            dlambda = math.radians(lon2 - lon1)
            a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
            return 2*R*math.atan2(math.sqrt(a), math.sqrt(1-a))

        total_km = 0
        prev = None

        for a in ordered_assignments:
            lat = a.pickup_request.latitude
            lng = a.pickup_request.longitude
            if lat and lng and prev:
                total_km += haversine(prev[0], prev[1], float(lat), float(lng))
            if lat and lng:
                prev = (float(lat), float(lng))

        avg_speed_kmh = 25  # Urban Kampala average
        duration_mins = (total_km / avg_speed_kmh * 60) + (len(ordered_assignments) * 10)  # 10 min per stop

        return {
            "total_distance_km": round(total_km, 2),
            "estimated_duration_mins": round(duration_mins),
            "stops": len(ordered_assignments),
            "fuel_estimate_liters": round(total_km / 10, 2),  # 10km/L average
        }


class AnalyticsDashboard:
    """Generates analytics data for dashboards"""

    def get_overview_stats(self):
        from apps.waste.models import PickupRequest
        from apps.payments.models import Payment
        from apps.accounts.models import User

        today = date.today()
        this_month_start = today.replace(day=1)
        last_month_start = (this_month_start - timedelta(days=1)).replace(day=1)

        revenue_this_month = (
            Payment.objects.filter(
                status='successful',
                created_at__date__gte=this_month_start
            ).aggregate(total=Avg('amount'))['total'] or 0
        )

        return {
            "total_users": User.objects.filter(role='resident').count(),
            "total_collectors": User.objects.filter(role='collector').count(),
            "total_requests_today": PickupRequest.objects.filter(created_at__date=today).count(),
            "total_requests_month": PickupRequest.objects.filter(created_at__date__gte=this_month_start).count(),
            "completion_rate": self._completion_rate(),
            "avg_response_time_hours": self._avg_response_time(),
            "revenue_this_month_ugx": float(revenue_this_month),
            "top_division": self._top_division(),
        }

    def _completion_rate(self):
        from apps.waste.models import PickupRequest
        total = PickupRequest.objects.count()
        if not total:
            return 0
        collected = PickupRequest.objects.filter(status='collected').count()
        return round((collected / total) * 100, 1)

    def _avg_response_time(self):
        """Average hours from request to assignment"""
        from apps.waste.models import Assignment
        assignments = Assignment.objects.select_related('pickup_request').filter(
            pickup_request__created_at__date__gte=date.today() - timedelta(days=30)
        )
        if not assignments.exists():
            return 0

        total_hours = 0
        count = 0
        for a in assignments:
            delta = a.assigned_at - a.pickup_request.created_at
            total_hours += delta.total_seconds() / 3600
            count += 1

        return round(total_hours / count, 1) if count else 0

    def _top_division(self):
        from apps.waste.models import PickupRequest
        result = (
            PickupRequest.objects
            .values('division')
            .annotate(count=Count('id'))
            .order_by('-count')
            .first()
        )
        return result['division'] if result else 'N/A'

    def get_monthly_trend(self, months=6):
        from apps.waste.models import PickupRequest
        from django.db.models.functions import TruncMonth
        from django.db.models import Count

        return list(
            PickupRequest.objects
            .filter(created_at__date__gte=date.today() - timedelta(days=months*30))
            .annotate(month=TruncMonth('created_at'))
            .values('month')
            .annotate(requests=Count('id'))
            .order_by('month')
        )

    def get_collector_performance(self):
        from apps.accounts.models import User
        from django.db.models import Count, Q

        return list(
            User.objects.filter(role='collector', is_active=True)
            .annotate(
                total=Count('assignments'),
                completed=Count('assignments', filter=Q(assignments__pickup_request__status='collected')),
                this_month=Count('assignments', filter=Q(
                    assignments__scheduled_date__gte=date.today().replace(day=1)
                )),
            )
            .order_by('-completed')
            .values('id', 'first_name', 'last_name', 'username', 'total', 'completed', 'this_month')
        )


# Singletons
demand_predictor = WasteDemandPredictor()
route_optimizer = RouteOptimizer()
analytics_dashboard = AnalyticsDashboard()
