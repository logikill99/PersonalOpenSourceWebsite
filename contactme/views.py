import logging

from django.conf import settings
from django.contrib import messages
from django.core.mail import send_mail
from django.shortcuts import redirect, render

from PersonalHomePage.ratelimit import is_rate_limited

from .forms import ContactForm, MessageForm
from .models import Contact, Message

logger = logging.getLogger(__name__)


def contact_view(request):
    if request.method == 'POST':
        if request.POST.get('website'):
            return redirect('success')

        contact_form = ContactForm(request.POST)
        message_form = MessageForm(request.POST)
        valid = contact_form.is_valid() and message_form.is_valid()

        if valid and is_rate_limited(request, key_prefix='contact', record=True):
            messages.error(request, 'Too many messages. Wait a minute and try again.')
            return render(
                request,
                'contact.html',
                {'contact_form': contact_form, 'message_form': message_form},
            )

        if valid:
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
            except Exception:
                logger.exception('Contact form email failed')
                messages.error(
                    request,
                    'Your message was saved, but email delivery failed. Try again later.',
                )
                return render(
                    request,
                    'contact.html',
                    {'contact_form': contact_form, 'message_form': message_form},
                )
            return redirect('success')
    else:
        contact_form = ContactForm()
        message_form = MessageForm()
    return render(request, 'contact.html', {'contact_form': contact_form, 'message_form': message_form})


def contact_success_view(request):
    return render(request, 'contact_success.html')
