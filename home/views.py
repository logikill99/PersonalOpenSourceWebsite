from django.shortcuts import render
from contactme.models import Contact, Message
from contactme.views import contact_view, contact_success_view

def home(request):
    return render(request, 'index.html')
