from django.urls import path, re_path

from . import views
from contactme.views import contact_view

urlpatterns = [
    path('', views.home, name='home'),
    re_path('contactme/',contact_view, name='contactme'),
]
