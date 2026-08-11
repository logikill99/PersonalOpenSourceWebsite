FROM python:3.13.0-alpine
LABEL authors="matthewlevin"
WORKDIR /app

COPY . /app
RUN apk add --no-cache sqlite
RUN pip3 install -r requirements.txt

# Build static assets for WhiteNoise. A dummy SECRET_KEY is required because
# settings.py refuses to import without one when DEBUG=False.
RUN SECRET_KEY=build-only-dummy DEBUG=False python3 manage.py collectstatic --noinput

RUN chmod +x /app/entrypoint.sh

ENV PYTHONUNBUFFERED=1
ENV DJANGO_SETTINGS_MODULE=PersonalHomePage.settings

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
