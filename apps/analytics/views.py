"""KLA WasteNet Pro — Analytics Views"""
import json
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from apps.accounts.views import role_required


@role_required('admin', 'super_admin', 'kcca_official')
def analytics_overview(request):
    from apps.analytics.services.ai_engine import analytics_dashboard, demand_predictor

    overview = analytics_dashboard.get_overview_stats()
    monthly = analytics_dashboard.get_monthly_trend(6)
    hotspots = demand_predictor.identify_hotspots()
    peak_hours = demand_predictor.predict_peak_hours()

    return render(request, 'admin/analytics.html', {
        'overview': overview,
        'monthly': json.dumps(monthly, default=str),
        'hotspots': hotspots,
        'peak_hours': json.dumps(peak_hours),
    })


@role_required('admin', 'super_admin', 'kcca_official')
def ai_predictions(request):
    from apps.analytics.services.ai_engine import demand_predictor
    division = request.GET.get('division', 'central')
    predictions = demand_predictor.predict_division_demand(division, days_ahead=14)
    return render(request, 'admin/ai_predictions.html', {
        'predictions': predictions,
        'division': division,
        'predictions_json': json.dumps(predictions),
    })


@role_required('admin', 'super_admin', 'kcca_official')
def collector_performance(request):
    from apps.analytics.services.ai_engine import analytics_dashboard
    perf = analytics_dashboard.get_collector_performance()
    return render(request, 'admin/collector_performance.html', {'performance': perf})
