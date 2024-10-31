from django.contrib import admin

from home.models import Skill, Experience


# Register your models here.
@admin.register(Skill)
class ExperienceAdmin(admin.ModelAdmin):
    pass


@admin.register(Experience)
class ExperienceAdmin(admin.ModelAdmin):
    pass
