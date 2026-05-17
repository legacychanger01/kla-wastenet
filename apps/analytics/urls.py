"""KLA WasteNet Pro — Analytics URLs"""
from django.urls import path
from apps.analytics import views

urlpatterns = [
    path('', views.analytics_overview, name='analytics_overview'),
    path('ai-predictions/', views.ai_predictions, name='ai_predictions'),
    path('collector-performance/', views.collector_performance, name='collector_performance'),
]
