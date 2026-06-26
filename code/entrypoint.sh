#!/bin/sh
set -e

echo "==> Menunggu PostgreSQL siap..."
python - <<'PYEOF'
import os
import sys
import time
import psycopg2

host = os.environ.get("POSTGRES_HOST", "db")
port = os.environ.get("POSTGRES_PORT", "5432")
db = os.environ.get("POSTGRES_DB", "simple_lms")
user = os.environ.get("POSTGRES_USER", "postgres")
password = os.environ.get("POSTGRES_PASSWORD", "postgres")

for attempt in range(30):
    try:
        conn = psycopg2.connect(host=host, port=port, dbname=db, user=user, password=password)
        conn.close()
        print("PostgreSQL siap.")
        sys.exit(0)
    except psycopg2.OperationalError:
        print(f"PostgreSQL belum siap, percobaan {attempt + 1}/30...")
        time.sleep(2)

print("PostgreSQL tidak merespons setelah 30 percobaan.")
sys.exit(1)
PYEOF

echo "==> Generate JWT signing key (jika belum ada)..."
if [ ! -f "jwt-signing.pem" ] || [ ! -f "jwt-signing.pub" ]; then
    python manage.py make_jwt_key
else
    echo "JWT key sudah ada, skip."
fi

echo "==> Menjalankan migrasi database..."
python manage.py migrate --noinput

echo "==> Menjalankan server..."
exec python manage.py runserver 0.0.0.0:8000