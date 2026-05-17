"""KLA WasteNet Pro — Accounts URLs"""
from django.urls import path
from apps.accounts import views

urlpatterns = [
    path('', views.home, name='home'),
    path('accounts/login/', views.login_view, name='login'),
    path('accounts/logout/', views.logout_view, name='logout'),
    path('accounts/register/', views.register_view, name='register'),
    path('accounts/profile/', views.profile_view, name='profile'),
    path('accounts/profile/edit/', views.profile_edit, name='profile_edit'),
    path('accounts/password/reset/', views.password_reset_request, name='password_reset'),
    path('accounts/2fa/setup/', views.setup_2fa, name='setup_2fa'),
    path('accounts/verify-email/<str:token>/', views.verify_email, name='verify_email'),

    # Dashboards
    path('dashboard/resident/', views.resident_dashboard, name='resident_dashboard'),
    path('dashboard/collector/', views.collector_dashboard, name='collector_dashboard'),
    path('dashboard/admin/', views.admin_dashboard, name='admin_dashboard'),
    path('dashboard/kcca/', views.kcca_dashboard, name='kcca_dashboard'),

    # Admin user management
    path('admin-panel/users/', views.manage_users, name='manage_users'),
    path('admin-panel/users/add-collector/', views.add_collector, name='add_collector'),
    path('admin-panel/users/<str:pk>/toggle/', views.toggle_user_status, name='toggle_user'),
    path('admin-panel/audit-logs/', views.audit_logs, name='audit_logs'),

    # Notifications
    path('notifications/', views.notifications_list, name='notifications'),
    path('notifications/<str:pk>/read/', views.mark_notification_read, name='mark_notification_read'),
    path('notifications/mark-all-read/', views.mark_all_read, name='mark_all_read'),
]
