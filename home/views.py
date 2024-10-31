import time

from django.shortcuts import render
from contactme.models import Contact, Message
from contactme.views import contact_view, contact_success_view
from blog.models import Category, Post
from PersonalHomePage.settings import (
    LISTED_EMAIL,
    LISTED_GITHUB,
    LISTED_LINKEDIN,
    LISTED_TWITTER,
    LISTED_DISCORD,
)
from home.models import Experience, Skill


def home(request):
    projects = Post.objects.filter(categories__name__contains="project").order_by(
        "-created_on"
    )
    languages = Skill.objects.filter(type="language")
    frameworks = Skill.objects.filter(type="framework")
    hobbies = Skill.objects.filter(type="hobby")
    return render(
        request,
        "index.html",
        {
            "projects": projects,
            "languages": languages,
            "frameworks": frameworks,
            "hobbies": hobbies,
            "linkedin": LISTED_LINKEDIN,
            "github": LISTED_GITHUB,
            "twitter": LISTED_TWITTER,
            "discord": LISTED_DISCORD,
            "email": LISTED_EMAIL,
        },
    )
