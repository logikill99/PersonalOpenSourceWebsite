import logging

from django.conf import settings
from django.contrib import messages
from django.core.mail import send_mail
from django.shortcuts import redirect, render

from PersonalHomePage.ratelimit import is_rate_limited

from .forms import ContactForm

logger = logging.getLogger(__name__)


def contact_view(request):
    if request.method == 'POST':
        if request.POST.get('website'):
            return redirect('success')

        form = ContactForm(request.POST)

        if form.is_valid():
            if is_rate_limited(request, key_prefix='contact', record=True):
                messages.error(request, 'Too many messages. Wait a minute and try again.')
                return render(request, 'contact.html', {'form': form})

            data = form.cleaned_data
            try:
                sent = send_mail(
                    'New Message',
                    f'You have a new message from {data["first_name"]} {data["last_name"]}.\n\n'
                    f'Email: {data["email"]}\n\n'
                    f'Phone Number: {data["phone_number"]}\n\n'
                    f'Message: {data["message"]}',
                    settings.DEFAULT_FROM_EMAIL,
                    [settings.EMAIL_HOST_USER],
                    fail_silently=False,
                )
                # send_mail returns the number of messages the backend
                # accepted. It can return 0 without raising (e.g. blank
                # EMAIL_HOST_USER yields an empty recipient list). Treat
                # anything other than exactly one accepted message as a
                # delivery failure instead of redirecting to success.
                if sent != 1:
                    raise RuntimeError(f'send_mail accepted {sent} messages, expected 1')
            except Exception:
                # Email-only policy: nothing is persisted, so a delivery
                # failure means the message is lost unless the visitor
                # retries. Keep their input in the re-rendered form.
                logger.exception('Contact form email failed')
                messages.error(
                    request,
                    'Sending failed. Your message was not delivered — '
                    'please try again in a minute.',
                )
                return render(request, 'contact.html', {'form': form})
            return redirect('success')
    else:
        form = ContactForm()
    return render(request, 'contact.html', {'form': form})


def contact_success_view(request):
    return render(request, 'contact_success.html')
