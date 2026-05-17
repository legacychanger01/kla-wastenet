# MySQL Setup Guide for KLA WasteNet Pro
# =========================================

## Option A: SQLite (Default — Zero Setup)

SQLite is configured by default in `.env`. No additional setup needed.
Simply run:

```bash
python manage.py migrate
python manage.py seed_data --all
python manage.py runserver
```

---

## Option B: MySQL Setup

### 1. Install MySQL (Ubuntu/Debian)

```bash
sudo apt update
sudo apt install mysql-server mysql-client libmysqlclient-dev -y
sudo systemctl start mysql
sudo systemctl enable mysql
```

### 2. Install MySQL (Windows)
Download MySQL Community Server from https://dev.mysql.com/downloads/mysql/

### 3. Install MySQL (macOS)
```bash
brew install mysql
brew services start mysql
```

### 4. Install Python MySQL driver
```bash
pip install mysqlclient
# OR if mysqlclient fails:
pip install PyMySQL
```

If using PyMySQL, add this to `config/__init__.py`:
```python
import pymysql
pymysql.install_as_MySQLdb()
```

### 5. Create the database

```bash
sudo mysql -u root -p
```

```sql
CREATE DATABASE kla_wastenet_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'kla_user'@'localhost' IDENTIFIED BY 'YourStrongPassword123!';
GRANT ALL PRIVILEGES ON kla_wastenet_db.* TO 'kla_user'@'localhost';
FLUSH PRIVILEGES;
EXIT;
```

### 6. Update your .env file

```env
DB_ENGINE=django.db.backends.mysql
DB_NAME=kla_wastenet_db
DB_USER=kla_user
DB_PASSWORD=YourStrongPassword123!
DB_HOST=127.0.0.1
DB_PORT=3306
```

### 7. Run migrations

```bash
python manage.py migrate
python manage.py seed_data --all
```

---

## Verify Connection

```bash
python manage.py dbshell
```

You should see the MySQL prompt. Type `\q` to exit.

---

## MySQL Performance Tips (already configured in settings)

- `utf8mb4` charset for full Unicode support (emojis etc.)
- `STRICT_TRANS_TABLES` mode for data integrity
- Connection pooling via `CONN_MAX_AGE=60`
- Proper indexing on all frequently-queried fields

---

## Common Issues

**`django.db.utils.OperationalError: (2003, "Can't connect to MySQL server")`**
→ MySQL isn't running: `sudo systemctl start mysql`

**`No module named 'MySQLdb'`**
→ Run: `pip install mysqlclient` or `pip install PyMySQL`

**`django.db.utils.OperationalError: (1049, "Unknown database")`**
→ Create the database first (see Step 5)

**Character encoding issues**
→ Ensure database was created with `utf8mb4` (see Step 5)
