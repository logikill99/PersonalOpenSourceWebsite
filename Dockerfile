FROM python:3.13.0-alpine
LABEL authors="matthewlevin"
WORKDIR /app

COPY . /app
RUN apk add --no-cache sqlite
RUN pip3 install django python-dotenv "django-phonenumber-field[phonenumbers]"
RUN ls -a
RUN pwd
ENV PYTHONUNBUFFERED=1
ENV DJANGO_SETTINGS_MODULE=PersonalHomePage.settings

RUN python3 manage.py makemigrations
RUN python3 manage.py migrate

EXPOSE 8000

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
#ENTRYPOINT ["python3", "manage.py", "runserver", "0.0.0.0:8000"]

