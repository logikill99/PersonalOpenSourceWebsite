from django.db import models
from phonenumber_field.modelfields import PhoneNumberField
from PersonalHomePage.settings import REGION


# Create your models here.
class Contact(models.Model):
    first_name = models.CharField(max_length=30)
    last_name = models.CharField(max_length=30)
    email = models.EmailField(null=False, blank=False)
    phone_number = PhoneNumberField(region=REGION)


class Message(models.Model):
    contact = models.ForeignKey(Contact, on_delete=models.CASCADE)
    message = models.TextField()
    time = models.DateTimeField(auto_now=True)