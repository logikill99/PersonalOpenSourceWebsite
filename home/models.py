from django.db import models


# Create your models here.
class MyModel(models.Model):
    pass


class Skill(models.Model):
    name = models.CharField(max_length=50)
    proficiency = models.CharField(max_length=30)
    description = models.TextField()
    type = models.CharField(max_length=15)
    url = models.URLField()

    def __str__(self):
        return self.name


class Experience(models.Model):
    title = models.CharField(max_length=50)
    organization = models.CharField(max_length=50)
    start_date = models.DateField()
    end_date = models.DateField()
    current = models.BooleanField()
    description = models.TextField()
    type = models.CharField(max_length=15)
    skills = models.ManyToManyField("Skill")
    url = models.URLField()

    def __str__(self):
        return self.title
