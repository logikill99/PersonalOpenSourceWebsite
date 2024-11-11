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
    LISTED_NAME,
    LISTED_TITLE,
)
from home.models import Experience, Skill


def home(request):
    projects = Post.objects.filter(categories__name__contains="project").order_by(
        "-created_on"
    )
    highlighted_skills = Skill.objects.filter(proficiency='Excellent')
    languages = Skill.objects.filter(type="language")
    frameworks = Skill.objects.filter(type="framework")
    hobbies = Skill.objects.filter(type="hobby")
    return render(
        request,
        "index.html",
        {
            "highlighted_skills": highlighted_skills,
            "projects": projects,
            "languages": languages,
            "frameworks": frameworks,
            "hobbies": hobbies,
            "linkedin": LISTED_LINKEDIN,
            "github": LISTED_GITHUB,
            "twitter": LISTED_TWITTER,
            "discord": LISTED_DISCORD,
            "email": LISTED_EMAIL,
            "name": LISTED_NAME,
            "title": LISTED_TITLE,
        },
    )


def about(request):
    projects = Post.objects.filter(categories__name__contains="project").order_by(
        "-created_on"
    )
    education_experiences = Experience.objects.filter(type="education").order_by(
        "-start_date"
    )
    work_experiences = Experience.objects.filter(type="work").order_by("-start_date")
    personal_experiences = Experience.objects.filter(type="personal").order_by(
        "-start_date"
    )

    languages = Skill.objects.filter(type="language")
    frameworks = Skill.objects.filter(type="framework")
    hobbies = Skill.objects.filter(type="hobby")
    other_skills = Skill.objects.filter(type="other")

    return render(
        request,
        "about.html",
        {
            "projects": projects,
            "languages": languages,
            "frameworks": frameworks,
            "other_skills": other_skills,
            "hobbies": hobbies,
            "education_experiences": education_experiences,
            "work_experiences": work_experiences,
            "personal_experiences": personal_experiences,
            "linkedin": LISTED_LINKEDIN,
            "github": LISTED_GITHUB,
            "twitter": LISTED_TWITTER,
            "discord": LISTED_DISCORD,
            "email": LISTED_EMAIL,
        },
    )
