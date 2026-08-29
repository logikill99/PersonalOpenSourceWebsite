# PII policy (2026-08-20): the contact form is email-only. Submissions are
# relayed to the site owner via SMTP and never persisted to the database.
from django import forms
from phonenumber_field.formfields import PhoneNumberField


class ContactForm(forms.Form):
    first_name = forms.CharField(max_length=30, required=True)
    last_name = forms.CharField(max_length=30, required=True)
    email = forms.EmailField(required=True)
    phone_number = PhoneNumberField(region='US', required=False)
    message = forms.CharField(
        max_length=5000,
        widget=forms.Textarea(attrs={'rows': 5}),
    )
