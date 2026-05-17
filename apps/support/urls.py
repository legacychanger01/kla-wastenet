"""KLA WasteNet Pro — Support URLs"""
from django.urls import path
from apps.support import views

urlpatterns = [
    path('', views.support_tickets, name='support_tickets'),
    path('new/', views.new_ticket, name='new_ticket'),
    path('<str:pk>/', views.ticket_detail, name='ticket_detail'),
    path('admin/', views.admin_tickets, name='admin_tickets'),
    path('<str:pk>/assign/', views.assign_ticket, name='assign_ticket'),
]
