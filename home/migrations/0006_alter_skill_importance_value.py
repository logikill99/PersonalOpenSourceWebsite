# Generated by Django 5.1.3 on 2024-11-18 17:48

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('home', '0005_skill_importance_value_alter_experience_end_date_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='skill',
            name='importance_value',
            field=models.SmallIntegerField(default=1),
        ),
    ]