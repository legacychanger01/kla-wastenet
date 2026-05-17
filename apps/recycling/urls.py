"""KLA WasteNet Pro — Recycling URLs"""
from django.urls import path
from apps.recycling import views

urlpatterns = [
    path('request/', views.recycling_request, name='recycling_request'),
    path('my-rewards/', views.my_rewards, name='my_rewards'),
    path('campaigns/', views.campaigns, name='campaigns'),
    path('admin/', views.admin_recycling, name='admin_recycling'),
]
