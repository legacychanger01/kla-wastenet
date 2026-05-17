"""KLA WasteNet Pro — Payment URLs"""
from django.urls import path
from apps.payments import views

urlpatterns = [
    path('', views.payment_dashboard, name='payment_dashboard'),
    path('initiate/', views.initiate_payment, name='initiate_payment'),
    path('verify/<str:reference>/', views.verify_payment_view, name='verify_payment'),
    path('receipt/<str:reference>/', views.payment_receipt, name='payment_receipt'),
    path('subscription/', views.subscription_plans, name='subscription_plans'),

    # Admin
    path('admin/', views.admin_payments, name='admin_payments'),

    # Webhooks
    path('webhooks/mtn/', views.mtn_webhook, name='mtn_webhook'),
    path('webhooks/flutterwave/', views.flutterwave_webhook, name='flutterwave_webhook'),
]
