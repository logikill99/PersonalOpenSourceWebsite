"""
URL configuration for PersonalHomePage project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.http import HttpResponse
from django.urls import include, path
from django.views.generic import TemplateView

from PersonalHomePage import views as project_views


def favicon(request):
    # Tiny inline SVG so /favicon.ico is not a 404 and is not the 1.jpg hero.
    svg = (
        "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'>"
        "<rect width='32' height='32' fill='#34302C'/>"
        "<text x='16' y='22' text-anchor='middle' font-size='16' fill='#E49B5D'>M</text>"
        "</svg>"
    )
    return HttpResponse(svg, content_type='image/svg+xml')


urlpatterns = [
    path('admin/', admin.site.urls),
    path('health/', project_views.health_check, name='health-check'),
    path('healthcheck/', project_views.health_check, name='healthcheck'),
    path('robots.txt', TemplateView.as_view(template_name='robots.txt', content_type='text/plain')),
    path('favicon.ico', favicon, name='favicon'),
    path('', include('home.urls')),
    path('contactme/', include('contactme.urls')),
    path('blog/', include('blog.urls')),
]
