from django.urls import path, re_path

from . import views
from contactme.views import contact_view
from blog.views import blog_index

urlpatterns = [
    path("", views.home, name="home"),
    path("contactme/", contact_view, name="contactme"),
    path("blog/", blog_index, name="blog"),
]
