# PersonalOpenSourceWebsite

This is the source code for my personal portfolio website that is written in Django (soon to be deployed on mslevin.dev).
it is meant to be a very drop in solution for anyone else who wants to use it or modify it. 

This website can be run in a docker container, or locally without docker. 

_**Running with Docker is easier unless you are making changes to the code and is recommended for beginners**_

# Installation

**Dependencies:** Docker, Git, SQLite3

**Clone the repo with:** ```git clone https://github.com/logikill99/PersonalOpenSourceWebsite.git```

**If you are running it locally not in a docker container:**

Python 3.10 or above

Django 5.1.0 or above

django-phonenumber-field

pillow for python

python-dotenv


or if you want to run the website without docker you can just run:
```pip3 install -r requirements.txt```

# Running

**Before anything else:**
you need to edit the .env file in the root directory of the project
the one provided in the repo is an example I strongly reccomend changing them to actual values before running **NOT CHANGING THE SAMPLE .ENV VALUES CAN BREAK THE APPLICATION**

Here is the sample .env file:
```
SECRET_KEY = "1234" # Set to a random string in production
DEBUG = True # Set to False in production
EMAIL_HOST_USER = "makesuretochangethis@sample.com" # Email that will be used in the contact section
EMAIL_HOST_PASSWORD = "thes isas ampl pswd" # follow these instructions to get an app password on gmail https://support.google.com/mail/answer/185833?hl=en
LISTED_EMAIL = "makesuretochangethis@sample.com" # Email that will be displayed on the website
LISTED_GITHUB = "https://github.com/logikill99" # Links to your github media
LISTED_LINKEDIN = "https://www.linkedin.com/in/matthew-levin-5976551a1/" # Links to your linkedin
LISTED_TWITTER = "" # Wip
LISTED_DISCORD = "" # Wip
LISTED_NAME = "Your Name" # this is the name that will show up throughout the site
LISTED_TITLE = "Full Stack Developer, QA Automation Specialist"
LISTED_IN_TEXT_TITLE = "Full Stack Developer and QA Automation Specialist"
ADMIN_EMAIL = "makesuretochangethis@sample.com" # the email that will recive admin notificatoins 
ADMIN_NAME = "Matt"
ALLOWED_HOSTS = "localhost" # this is your domain that is hosting the website just leave it as localhost when debugging and running locally
```

## RUNNING IN DOCKER

**Warning: The dockerfile in the root directory contains sample superuser credentials please change them before deploying to productoion**


### On MacOS/linux
Just do:
```./run.sh```
you may have to give run.sh execute permission (sometimes when doing a git clone it doesn't give the file execute perms)

Once that has finished starting up, go to localhost:8000 in your browser

to add things to the database (and the page) you can go to `localhost:8000/admin` and login with username:`admin` password:`admin` 
these can be changed by changing the following values in the Dockerfile:
```
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
```

After changing those values be sure to delete the docker image and container and run `run.sh` again

### on Windows:
Just right click run.bat and run it as an administrator

Once that has finished starting up, go to localhost:8000 in your browser

to add things to the database (and the page) you can go to `localhost:8000/admin` and login with username:`admin` password:`admin` 
these can be changed by changing the following values in the Dockerfile:
```
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
```

After changing those values be sure to delete the docker image and container and run `run.bat` again

**RUNNING WITHOUT DOCKER**
Once all dependencies are installed run the following commands:

```
python3 manage.py makemigrations
python3 manage.py migrate
python3 manage.py createsuperuser
python3 manage.py runserver
```
Follow the prompts to create a superuser (this is what you will use to login to the /admin area)
If all the dependencies are installed correctly this should work regardless of operating system. 

then you can go to `localhost:8000` in your browser and everything should be set!

if you want to add stuff to the database go to `localhost:8000/admin` and login with the credentials you made for the superuser

# Setting up your database

The database contains almost everything of substance for the site, all skills, blog posts, projects, and most descriptions are managed by the database. I made some weird design decisions when making the database models but I did do most of them to make the site more extensible. Pretty much all of it can be done by going to /admin
