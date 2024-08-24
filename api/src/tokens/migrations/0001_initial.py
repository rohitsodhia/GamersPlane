# Generated by Django 5.1 on 2024-08-23 13:42

import django.db.models.deletion
import tokens.models.token
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("users", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Token",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "token_type",
                    models.CharField(
                        choices=[
                            ("aa", "Account Activation"),
                            ("pr", "Password Reset"),
                        ],
                        max_length=2,
                    ),
                ),
                (
                    "token",
                    models.CharField(
                        default=tokens.models.token.generate_token, max_length=36
                    ),
                ),
                ("requestedOn", models.DateTimeField(auto_now_add=True)),
                ("used", models.DateTimeField(default=None, null=True)),
                (
                    "user",
                    models.ForeignKey(
                        db_column="userId",
                        on_delete=django.db.models.deletion.PROTECT,
                        to="users.user",
                    ),
                ),
            ],
            options={
                "db_table": "tokens",
            },
        ),
        migrations.CreateModel(
            name="AccountActivationToken",
            fields=[],
            options={
                "proxy": True,
                "indexes": [],
                "constraints": [],
            },
            bases=("tokens.token",),
        ),
        migrations.CreateModel(
            name="PasswordResetToken",
            fields=[],
            options={
                "proxy": True,
                "indexes": [],
                "constraints": [],
            },
            bases=("tokens.token",),
        ),
        migrations.AddIndex(
            model_name="token",
            index=models.Index(fields=["token"], name="tokens_token_57b770_idx"),
        ),
    ]
