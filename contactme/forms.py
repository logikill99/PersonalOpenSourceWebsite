# coolSite/forms.py
from django import forms
from .models import Contact, Message
from phonenumber_field.formfields import PhoneNumberField


class ContactForm(forms.ModelForm):
    first_name = forms.CharField(max_length=30, required=True)
    last_name = forms.CharField(max_length=30, required=True)
    email = forms.EmailField(required=True)
    phone_number = PhoneNumberField(region='US', required=False)

    class Meta:
        model = Contact
        fields = '__all__'


class MessageForm(forms.Form):
    message = forms.CharField(widget=forms.Textarea)

    class Meta:
        model = Message
        fields = ['message']
