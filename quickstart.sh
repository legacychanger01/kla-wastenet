#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════
# KLA WasteNet Pro — Quick Start Script
# Supports SQLite (default) or MySQL
# ═══════════════════════════════════════════════════════════════════════════

set -e  # Exit on any error

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  🌿  KLA WasteNet Pro — Quick Start               ${NC}"
echo -e "${GREEN}  Smart Waste Management · Kampala, Uganda          ${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════${NC}"
echo ""

# Step 1: Check Python
echo -e "${BLUE}[1/7] Checking Python version...${NC}"
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo -e "  ✓ Python $python_version found"

# Step 2: Create virtual environment
echo -e "${BLUE}[2/7] Setting up virtual environment...${NC}"
if [ ! -d "venv" ]; then
  python3 -m venv venv
  echo -e "  ✓ Virtual environment created"
else
  echo -e "  ✓ Virtual environment already exists"
fi
source venv/bin/activate

# Step 3: Install dependencies
echo -e "${BLUE}[3/7] Installing dependencies...${NC}"
pip install --upgrade pip --quiet
# Install core deps only (lighter set for quick start)
pip install Django==5.0.6 django-environ==0.11.2 djangorestframework==3.15.2 \
    drf-spectacular==0.27.2 django-cors-headers==4.3.1 \
    channels==4.1.0 whitenoise==6.7.0 Pillow==10.3.0 \
    django-axes==6.4.0 django-crispy-forms==2.1 crispy-bootstrap5==2024.2 \
    django-pwa==1.1.0 openpyxl==3.1.3 reportlab==4.2.2 \
    requests==2.32.3 --quiet
echo -e "  ✓ Core packages installed"

# For MySQL support (optional)
if [ "$1" == "--mysql" ]; then
  echo -e "  Installing MySQL driver..."
  pip install mysqlclient --quiet 2>/dev/null || pip install PyMySQL --quiet
  echo -e "  ✓ MySQL driver installed"
fi

# Step 4: Configure environment
echo -e "${BLUE}[4/7] Configuring environment...${NC}"
if [ ! -f ".env" ]; then
  cp .env.example .env 2>/dev/null || true
  echo -e "  ✓ .env file created from template"
else
  echo -e "  ✓ .env file already exists"
fi

# Step 5: Set up database
echo -e "${BLUE}[5/7] Setting up database...${NC}"
export DJANGO_SETTINGS_MODULE=config.settings.development
python manage.py migrate --run-syncdb 2>/dev/null || python manage.py migrate
echo -e "  ✓ Database migrations applied"

# Step 6: Seed initial data
echo -e "${BLUE}[6/7] Seeding initial data...${NC}"
python manage.py seed_data --categories --superuser 2>/dev/null || true
echo -e "  ✓ Waste categories and demo users created"

# Step 7: Collect static files
echo -e "${BLUE}[7/7] Collecting static files...${NC}"
python manage.py collectstatic --noinput --clear --quiet 2>/dev/null || true
echo -e "  ✓ Static files ready"

echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  ✅  Setup Complete!                               ${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════${NC}"
echo ""
echo -e "  ${BLUE}Start the server:${NC}"
echo -e "  source venv/bin/activate && python manage.py runserver"
echo ""
echo -e "  ${BLUE}Open in browser:${NC} http://localhost:8000"
echo ""
echo -e "  ${YELLOW}Demo Login Credentials:${NC}"
echo -e "  ┌──────────────────┬────────────────────┬─────────────────────┐"
echo -e "  │ Role             │ Username           │ Password            │"
echo -e "  ├──────────────────┼────────────────────┼─────────────────────┤"
echo -e "  │ Super Admin      │ superadmin         │ KLAAdmin@2024!      │"
echo -e "  │ KCCA Official    │ kcca_official      │ KLAOfficial@2024!   │"
echo -e "  │ Collector        │ collector_01        │ KLACollect@2024!    │"
echo -e "  │ Resident         │ resident_01         │ KLAResident@2024!   │"
echo -e "  └──────────────────┴────────────────────┴─────────────────────┘"
echo ""
echo -e "  ${BLUE}API Documentation:${NC}  http://localhost:8000/api/docs/"
echo -e "  ${BLUE}Django Admin:${NC}       http://localhost:8000/django-admin/"
echo ""
echo -e "  ${YELLOW}Database:${NC} SQLite (default) · See docs/MYSQL_SETUP.md for MySQL"
echo ""
