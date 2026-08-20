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

# Rate-limiter cache table (DatabaseCache). Idempotent: no-op if it exists.
python3 manage.py createcachetable

# Create superuser if credentials are provided via environment variables.
# Do not swallow real failures: "user already exists" is the only expected miss.
if [ -n "$DJANGO_SUPERUSER_USERNAME" ] && [ -n "$DJANGO_SUPERUSER_PASSWORD" ]; then
    if python3 manage.py createsuperuser --noinput; then
        echo "Created superuser '$DJANGO_SUPERUSER_USERNAME'."
    else
        if python3 manage.py shell -c 'import os, sys; from django.contrib.auth import get_user_model; sys.exit(0 if get_user_model().objects.filter(username=os.environ["DJANGO_SUPERUSER_USERNAME"]).exists() else 1)'; then
            echo "Superuser '$DJANGO_SUPERUSER_USERNAME' already exists."
        else
            echo "ERROR: createsuperuser failed and user '$DJANGO_SUPERUSER_USERNAME' does not exist." >&2
            exit 1
        fi
    fi
fi

# SQLite does not like a herd of writers. Cap workers even if Railway is generous.
WORKERS=${WEB_CONCURRENCY:-2}
if [ "$WORKERS" -gt 3 ]; then
    echo "WARNING: capping WEB_CONCURRENCY from $WORKERS to 3 (SQLite)."
    WORKERS=3
fi

# Start gunicorn
exec gunicorn PersonalHomePage.wsgi:application \
    --bind 0.0.0.0:${PORT:-8000} \
    --workers "$WORKERS" \
    --timeout ${GUNICORN_TIMEOUT:-30} \
    --access-logfile - \
    --error-logfile -
