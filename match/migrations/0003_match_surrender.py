# Generated by Django 4.2.1 on 2023-07-31 05:21

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('match', '0002_award_user'),
    ]

    operations = [
        migrations.AddField(
            model_name='match',
            name='Surrender',
            field=models.IntegerField(default=0),
        ),
    ]