"""
KLA WasteNet Pro — URL Configuration
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework.routers import DefaultRouter
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView

# API Router
router = DefaultRouter()
# Waste
from apps.waste.api.views import (
    WasteCategoryViewSet, PickupRequestViewSet, AssignmentViewSet,
    CollectorLocationViewSet, SmartBinViewSet, WasteReportViewSet
)
router.register('waste/categories', WasteCategoryViewSet, basename='api-categories')
router.register('waste/requests', PickupRequestViewSet, basename='api-requests')
router.register('waste/assignments', AssignmentViewSet, basename='api-assignments')
router.register('waste/locations', CollectorLocationViewSet, basename='api-locations')
router.register('waste/smart-bins', SmartBinViewSet, basename='api-smart-bins')
router.register('waste/reports', WasteReportViewSet, basename='api-reports')

urlpatterns = [
    # Django Admin
    path('django-admin/', admin.site.urls),

    # Main Web Application
    path('', include('apps.accounts.urls')),
    path('waste/', include('apps.waste.urls')),
    path('payments/', include('apps.payments.urls')),
    path('analytics/', include('apps.analytics.urls')),
    path('recycling/', include('apps.recycling.urls')),
    path('support/', include('apps.support.urls')),

    # REST API v1
    path('api/v1/', include(router.urls)),
    path('api/v1/auth/', include('rest_framework.urls')),

    # API Documentation
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),

    # Health Check
    path('health/', include('health_check.urls')),

    # PWA
    path('', include('pwa.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    try:
        import debug_toolbar
        urlpatterns = [path('__debug__/', include(debug_toolbar.urls))] + urlpatterns
    except ImportError:
        pass

# Customize admin site
admin.site.site_header = "KLA WasteNet Administration"
admin.site.site_title = "KLA WasteNet"
admin.site.index_title = "Smart Waste Management Platform"
