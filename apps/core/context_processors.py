"""
KLA WasteNet Pro — Context Processors
Global template context available in all templates
"""
from django.conf import settings


def site_settings(request):
    return {
        'SITE_NAME': 'KLA WasteNet',
        'SITE_URL': settings.SITE_URL,
        'GOOGLE_MAPS_KEY': settings.GOOGLE_MAPS_API_KEY,
        'VERSION': '2.0.0',
        'DIVISIONS': [
            ('central', 'Central Division'),
            ('kawempe', 'Kawempe Division'),
            ('makindye', 'Makindye Division'),
            ('nakawa', 'Nakawa Division'),
            ('rubaga', 'Rubaga Division'),
        ],
    }
