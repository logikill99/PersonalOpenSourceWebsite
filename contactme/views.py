from django.shortcuts import render, redirect
from .models import Contact, Message
from .forms import ContactForm, MessageForm
from django.shortcuts import render
from django.http import HttpResponse
from django.core.mail import send_mail
from django.conf import settings


def contact_view(request):
    if request.method == 'POST':
        contact_form = ContactForm(request.POST)
        message_form = MessageForm(request.POST)

        if contact_form.is_valid() and message_form.is_valid():
            if not Contact.objects.filter(email=contact_form.cleaned_data['email']).exists():
                contact_form.save()

            contact = Contact.objects.get(email=contact_form.cleaned_data['email'])
            message = Message(contact=contact, message=message_form.cleaned_data['message'])
            message.save()
            try:
                send_mail(
                    'New Message',
                    f'You have a new message from {contact.first_name} {contact.last_name}.\n\n'
                    f'Email: {contact.email}\n\n'
                    f'Phone Number: {contact.phone_number}\n\n'
                    f'Message: {message.message}',
                    settings.EMAIL_HOST_USER,
                    [settings.EMAIL_HOST_USER],
                    fail_silently=False,
                )
            except Exception as e:
                return HttpResponse(f'Error: {e}') # TODO: Add a better error page
            return redirect('success')
    else:
        contact_form = ContactForm()
        message_form = MessageForm()
    return render(request, 'contact.html', {'contact_form': contact_form, 'message_form': message_form})


def contact_success_view(request):
    return render(request, 'contact_success.html')
