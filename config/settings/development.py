"""
KLA WasteNet Pro — Development Settings
Uses SQLite by default (zero-config).  Switch to MySQL by setting
DB_ENGINE=django.db.backends.mysql in your .env file.
"""
from .base import *

DEBUG = True
ALLOWED_HOSTS = ['*']

# ─── Email (Console — no SMTP needed in dev) ─────────────────────────────────
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# ─── SQLite override (ensures dev always uses SQLite unless .env says otherwise)
import environ as _environ
_env = _environ.Env()
_db_engine = _env('DB_ENGINE', default='django.db.backends.sqlite3')
if _db_engine == 'django.db.backends.sqlite3':
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / _env('DB_NAME', default='kla_wastenet.db'),
            'OPTIONS': {'timeout': 20},
        }
    }

# ─── Cache (local memory if Redis not available) ─────────────────────────────
try:
    import redis as _redis_client
    _r = _redis_client.from_url(REDIS_URL)
    _r.ping()
except Exception:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        }
    }
    SESSION_ENGINE = 'django.contrib.sessions.backends.db'

# ─── Brute-Force (disabled in dev) ───────────────────────────────────────────
AXES_ENABLED = False

# ─── CORS (allow all in dev) ──────────────────────────────────────────────────
CORS_ALLOW_ALL_ORIGINS = True

# ─── Relaxed Security ────────────────────────────────────────────────────────
CSRF_COOKIE_SECURE = False
SESSION_COOKIE_SECURE = False
SECURE_SSL_REDIRECT = False

# ─── Debug Toolbar (install debug-toolbar to use) ────────────────────────────
try:
    import debug_toolbar
    INSTALLED_APPS = INSTALLED_APPS + ['debug_toolbar']
    MIDDLEWARE = ['debug_toolbar.middleware.DebugToolbarMiddleware'] + MIDDLEWARE
    INTERNAL_IPS = ['127.0.0.1']
except ImportError:
    pass
