# 🌿 KLA WasteNet Pro
## Smart Waste Management Platform for Kampala Capital City Authority (KCCA)

[![CI/CD Pipeline](https://github.com/klawastenet/app/actions/workflows/ci_cd.yml/badge.svg)](https://github.com/klawastenet/app/actions)
[![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python)](https://python.org)
[![Django](https://img.shields.io/badge/Django-5.0-green?logo=django)](https://djangoproject.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-blue?logo=postgresql)](https://postgresql.org)
[![Redis](https://img.shields.io/badge/Redis-7-red?logo=redis)](https://redis.io)
[![PWA](https://img.shields.io/badge/PWA-Enabled-purple)](https://web.dev/progressive-web-apps/)

---

A production-ready, AI-powered smart city waste management platform serving thousands of residents across all five Kampala divisions. Built on Django 5, PostgreSQL, Redis, Celery, and Django Channels with full REST API support, mobile money integrations, real-time GPS tracking, and AI-powered analytics.

---

## ✨ Key Features

### 🏛️ Multi-Role System
| Role | Capabilities |
|------|-------------|
| **Super Admin** | Full system access, user management, all reports |
| **KCCA Official** | City-wide analytics, division KPIs, revenue dashboards |
| **Division Admin** | Manage requests, assign collectors, zone reports |
| **Resident** | Submit requests, live tracking, payments, recycling |
| **Waste Collector** | View assignments, GPS tracking, status updates |
| **Recycling Company** | Accept recycling requests, manage reward points |

### 💳 Payment Gateways
- **MTN Mobile Money** — USSD-based push payment to subscriber's MTN number
- **Airtel Money** — Direct Airtel Money collection via API
- **Flutterwave** — Card, bank transfer, and mobile money via hosted checkout
- **Webhook processing** — Async payment verification via Celery

### 📍 Real-Time GPS Tracking
- Collector location updates every 10 seconds via WebSocket
- Residents see live collector position on interactive map
- Optimized collection routes using nearest-neighbor algorithm
- Estimated arrival time calculations

### 🤖 AI Analytics
- Demand forecasting by division using historical patterns
- Day-of-week seasonality modeling
- Hotspot identification across Kampala
- Collector performance scoring and ranking
- Auto-assignment of requests to least-loaded collectors

### 📱 Progressive Web App (PWA)
- Installable on Android and iOS home screens
- Offline support via Service Worker caching
- Background sync for location updates
- Push notifications via Firebase Cloud Messaging

### 🔐 Enterprise Security
- Role-based access control (RBAC)
- Two-factor authentication (TOTP via django-otp)
- Brute-force protection (django-axes, 5 attempt limit)
- Full audit logging of all sensitive actions
- CSRF, XSS, clickjacking protection
- Rate limiting on auth and API endpoints
- Encrypted sensitive data at rest
- Security headers (HSTS, CSP, X-Frame-Options)

### ♻️ Recycling Management
- Material-specific recycling requests (plastic, paper, e-waste, organic…)
- Reward points ledger with earn/redeem/expire transactions
- Environmental impact tracking (CO₂ savings, kg recycled)
- KCCA environmental awareness campaigns

### 📊 Reports & Exports
- PDF reports via ReportLab
- Excel exports via openpyxl (formatted with headers and branding)
- CSV exports for data analysis
- Division-level analytics
- Collector performance metrics
- Monthly revenue reports by gateway

---

## 🏗️ Architecture

```
kla_wastenet_pro/
├── apps/
│   ├── core/              # Middleware, pagination, context processors
│   ├── accounts/          # User model, auth, subscriptions, audit logs
│   ├── waste/             # Pickup requests, assignments, GPS, smart bins
│   ├── payments/          # MTN, Airtel, Flutterwave, invoicing
│   ├── notifications/     # SMS, email, FCM push, in-app
│   ├── analytics/         # AI predictions, report exporter, dashboards
│   ├── recycling/         # Recycling requests, rewards, campaigns
│   └── support/           # Support tickets, messaging
├── config/
│   ├── settings/          # base.py, development.py, production.py
│   ├── urls.py            # Main URL routing
│   ├── celery.py          # Celery + Beat configuration
│   ├── asgi.py            # ASGI (WebSocket) application
│   └── wsgi.py            # WSGI application
├── templates/             # Jinja-free Django templates
├── static/                # CSS, JS, images, service worker
├── tests/                 # Pytest test suite
├── .env.example           # Environment variable template
├── requirements.txt       # Python dependencies
└── .github/workflows/     # CI/CD GitHub Actions
```

---

## 🚀 Quick Start

### Prerequisites
- Python 3.12+
- PostgreSQL 16+
- Redis 7+

### Option A: Local Development

```bash
# 1. Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Edit .env — minimum required: SECRET_KEY, DB_* settings

# 4. Set up PostgreSQL database
createdb kla_wastenet_db
createuser kla_user

# 5. Run migrations
export DJANGO_SETTINGS_MODULE=config.settings.development
python manage.py migrate

# 6. Seed initial data
python manage.py seed_data --all

# 7. Start development server
python manage.py runserver

# 8. Start Celery (separate terminal)
celery -A config.celery worker --loglevel=info

# 9. Start Celery Beat (separate terminal)
celery -A config.celery beat --loglevel=info
```

---

## 🔑 Demo Credentials

| Role | Username | Password |
|------|----------|----------|
| Super Admin | `superadmin` | `KLAAdmin@2024!` |
| KCCA Official | `kcca_official` | `KLAOfficial@2024!` |
| Division Admin | `admin_kawempe` | `KLAAdmin@2024!` |
| Collector | `collector_01` | `KLACollect@2024!` |
| Resident | `resident_01` | `KLAResident@2024!` |

---

## 🔌 REST API

Full OpenAPI 3.0 documentation available at:
- **Swagger UI**: http://localhost:8000/api/docs/
- **ReDoc**: http://localhost:8000/api/redoc/
- **Schema JSON**: http://localhost:8000/api/schema/

### Authentication
```bash
# Get JWT token pair
curl -X POST http://localhost:8000/api/v1/auth/token/ \
     -H "Content-Type: application/json" \
     -d '{"username": "resident_01", "password": "KLAResident@2024!"}'

# Use access token
curl http://localhost:8000/api/v1/waste/requests/ \
     -H "Authorization: Bearer <access_token>"
```

### Key Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/waste/categories/` | List waste categories |
| POST | `/api/v1/waste/requests/` | Create pickup request |
| GET | `/api/v1/waste/requests/` | List my requests |
| POST | `/api/v1/waste/locations/` | Update collector GPS |
| GET | `/api/v1/waste/locations/live_collectors/` | Live collector positions |
| GET | `/api/v1/waste/smart-bins/critical/` | Critical smart bins |
| POST | `/api/v1/waste/assignments/{id}/update_status/` | Update assignment status |

---

## 🐳 Production Deployment

### Environment Variables (minimum required)
```bash
SECRET_KEY=your-50-char-minimum-secret-key
DEBUG=False
ALLOWED_HOSTS=yourdomain.com
DB_NAME=kla_wastenet_db
DB_USER=kla_user
DB_PASSWORD=strong-password
DB_HOST=localhost
REDIS_URL=redis://localhost:6379/0
MTN_MOMO_PRIMARY_KEY=...
AIRTEL_CLIENT_ID=...
FLW_SECRET_KEY=...
AT_API_KEY=...
GOOGLE_MAPS_API_KEY=...
```

### Deploy on Render / Railway
1. Push to GitHub
2. Connect your repo to Render/Railway
3. Set environment variables
4. Set build command: `pip install -r requirements.txt && python manage.py collectstatic --noinput && python manage.py migrate`
5. Set start command: `gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 3`

---

## 🧪 Testing

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
coverage run -m pytest tests/
coverage report --show-missing

# Run specific test class
pytest tests/test_core.py::TestPickupRequest -v

# Run only fast unit tests
pytest tests/ -m "not integration" -v
```

---

## 🗺️ Kampala Divisions Covered

| Division | Area Coverage |
|----------|--------------|
| **Central** | CBD, Old Kampala, Nakasero, Kololo |
| **Kawempe** | Kawempe, Mpererwe, Bwaise, Mulago |
| **Makindye** | Makindye, Ggaba, Nsambya, Buziga |
| **Nakawa** | Nakawa, Naguru, Kyambogo, Portbell |
| **Rubaga** | Rubaga, Namirembe, Mutundwe, Lubaga |

---

## 📄 License

Proprietary — Developed for Kampala Capital City Authority (KCCA).
All rights reserved. © 2024 KLA WasteNet Team.

---

## 🤝 Contributing

1. Fork the repository
2. Create feature branch: `git checkout -b feature/amazing-feature`
3. Commit changes: `git commit -m 'feat: add amazing feature'`
4. Push branch: `git push origin feature/amazing-feature`
5. Open Pull Request — CI will run tests automatically

---

*Built with ❤️ for a cleaner Kampala* 🌿
# kla-wastenet
