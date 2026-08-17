import logging
from time import monotonic

from django.conf import settings
from django.contrib import messages
from django.core.mail import send_mail
from django.shortcuts import redirect, render

from .forms import ContactForm, MessageForm
from .models import Contact, Message

logger = logging.getLogger(__name__)

_RATE_WINDOW_SECONDS = 60
_RATE_MAX_POSTS = 3


def _rate_limited(request) -> bool:
    now = monotonic()
    stamps = [ts for ts in request.session.get('contact_post_times', []) if now - ts < _RATE_WINDOW_SECONDS]
    if len(stamps) >= _RATE_MAX_POSTS:
        request.session['contact_post_times'] = stamps
        return True
    stamps.append(now)
    request.session['contact_post_times'] = stamps
    return False


def contact_view(request):
    if request.method == 'POST':
        if request.POST.get('website'):
            return redirect('success')

        if _rate_limited(request):
            messages.error(request, 'Too many messages. Wait a minute and try again.')
            contact_form = ContactForm(request.POST)
            message_form = MessageForm(request.POST)
            return render(
                request,
                'contact.html',
                {'contact_form': contact_form, 'message_form': message_form},
            )

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
