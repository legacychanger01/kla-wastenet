"""KLA WasteNet Pro — Waste URLs"""
from django.urls import path
from apps.waste import views

urlpatterns = [
    # Resident
    path('request/new/', views.make_request, name='make_request'),
    path('requests/', views.my_requests, name='my_requests'),
    path('requests/<str:pk>/', views.request_detail, name='request_detail'),
    path('requests/<str:pk>/rate/', views.submit_rating, name='submit_rating'),

    # Collector
    path('collector/assignment/<str:pk>/update/', views.update_pickup_status, name='update_pickup_status'),
    path('collector/location/update/', views.update_my_location, name='update_location'),

    # Admin
    path('admin-panel/requests/', views.manage_requests, name='manage_requests'),
    path('admin-panel/requests/<str:pk>/assign/', views.assign_request, name='assign_request'),
    path('admin-panel/reports/', views.reports_view, name='reports'),
    path('admin-panel/reports/export/<str:format_type>/', views.export_report, name='export_report'),
    path('admin-panel/smart-bins/', views.smart_bins_view, name='smart_bins'),
    path('admin-panel/routes/optimize/', views.optimize_routes, name='optimize_routes'),
]
