#!/bin/sh
set -e

# If DATABASE_PATH is set (e.g. /data/db.sqlite3 on a Railway volume), make
# sure the parent directory exists so SQLite can create the file.
if [ -n "$DATABASE_PATH" ]; then
    DB_DIR=$(dirname "$DATABASE_PATH")
    mkdir -p "$DB_DIR"
fi

# Apply database migrations
python3 manage.py migrate --noinput

# Create superuser if credentials are provided via environment variables
# This is idempotent: it will not fail if the superuser already exists.
if [ -n "$DJANGO_SUPERUSER_USERNAME" ] && [ -n "$DJANGO_SUPERUSER_PASSWORD" ]; then
    python3 manage.py createsuperuser --noinput || true
fi

# Start gunicorn
exec gunicorn PersonalHomePage.wsgi:application \
    --bind 0.0.0.0:${PORT:-8000} \
    --workers ${WEB_CONCURRENCY:-2} \
    --timeout ${GUNICORN_TIMEOUT:-30} \
    --access-logfile - \
    --error-logfile -
