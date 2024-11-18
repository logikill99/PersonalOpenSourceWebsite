from logging import lastResort

from django.db.models.base import ModelState
from django.shortcuts import render
from django.template.defaultfilters import title

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
    HOMEPAGE_IMAGE_CAPTION
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
            "image_caption": HOMEPAGE_IMAGE_CAPTION
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
    
    current_job = work_experiences.filter(current=1).first()
    current_education = education_experiences.filter(current=1).first()
    most_important_languages = languages.order_by("-importance_value")[:3]
    most_important_frameworks = frameworks.order_by("-importance_value")[:4]
    last_most_important_language = languages.order_by("-importance_value")[3:4].first()
    last_most_important_framework = frameworks.order_by("-importance_value")[4:5].first()

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
            "current_job": current_job,
            "current_education": current_education,
            "most_important_languages": most_important_languages,
            "most_important_frameworks": most_important_frameworks,
            "last_most_important_language": last_most_important_language,
            "last_most_important_framework": last_most_important_framework,
            "name": LISTED_NAME,
            "title": LISTED_TITLE
        },
    )
