FROM python:3.13.0-alpine
LABEL authors="matthewlevin"
WORKDIR /app

COPY . /app
RUN apk add --no-cache sqlite
RUN pip3 install -r requirements.txt
RUN ls -a
RUN pwd
ENV PYTHONUNBUFFERED=1
ENV DJANGO_SETTINGS_MODULE=PersonalHomePage.settings

# TODO: CHANGE THESE IN PRODUCTION
# Change me!
ENV DJANGO_SUPERUSER_PASSWORD=admin
# Change me too!
ENV DJANGO_SUPERUSER_USERNAME=admin
# Change me three!
ENV DJANGO_SUPERUSER_EMAIL=changeme@sample.com

RUN python3 manage.py makemigrations
RUN python3 manage.py migrate
RUN python3 manage.py createsuperuser --noinput

EXPOSE 8000

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
