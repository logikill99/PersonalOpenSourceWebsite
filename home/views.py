from django.shortcuts import render
from contactme.models import Contact, Message
from contactme.views import contact_view, contact_success_view
from blog.models import Category, Post


def home(request):
    projects = Post.objects.filter(categories__name__contains="project").order_by(
        "-created_on"
    )
    return render(request, "index.html", {"projects": projects})
