# Generated by Django 2.2.7 on 2019-11-11 03:47

from django.db import migrations, models
import django_mysql.models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="System",
            fields=[
                (
                    "id",
                    models.CharField(max_length=20, primary_key=True, serialize=False),
                ),
                ("name", models.CharField(max_length=40)),
                ("sortName", models.CharField(max_length=40)),
                ("publisher", django_mysql.models.JSONField(default=dict)),
                ("generes", django_mysql.models.JSONField(default=dict)),
                ("basics", django_mysql.models.JSONField(default=dict)),
                ("hasCharSheet", models.BooleanField(default=True)),
                ("enabled", models.BooleanField(default=True)),
                ("createdOn", models.DateTimeField(auto_now_add=True)),
                ("updatedOn", models.DateTimeField(auto_now=True)),
            ],
            options={"db_table": "systems"},
        )
    ]
