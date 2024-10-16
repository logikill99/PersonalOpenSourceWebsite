from django.contrib import admin

from contactme.models import Contact, Message


# Register your models here.
@admin.register(Contact)
class MessageAdmin(admin.ModelAdmin):
    pass


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    pass