FROM python:3.13.0-alpine
LABEL authors="matthewlevin"
WORKDIR /app

# su-exec: drop root -> appuser in entrypoint.sh after chowning the volume.
RUN apk add --no-cache sqlite su-exec \
    && addgroup -g 10001 appuser \
    && adduser -D -u 10001 -G appuser appuser

COPY . /app
RUN pip3 install -r requirements.txt

# Build static assets for WhiteNoise. A dummy SECRET_KEY is required because
# settings.py refuses to import without one when DEBUG=False.
RUN SECRET_KEY=build-only-dummy DEBUG=False python3 manage.py collectstatic --noinput

# /app stays root-owned (read-only to appuser): running code must not be
# able to modify itself. The database belongs on the volume (DATABASE_PATH).
# Precompile bytecode since appuser cannot write __pycache__ at runtime.
RUN chmod +x /app/entrypoint.sh && python3 -m compileall -q /app

ENV PYTHONUNBUFFERED=1
ENV DJANGO_SETTINGS_MODULE=PersonalHomePage.settings

EXPOSE 8000

# No USER directive: the entrypoint must start as root to chown the Railway
# volume mount (which arrives root-owned), then it unconditionally drops to
# appuser via su-exec before running migrations or gunicorn. Nothing
# application-facing ever executes as root.
ENTRYPOINT ["/app/entrypoint.sh"]
