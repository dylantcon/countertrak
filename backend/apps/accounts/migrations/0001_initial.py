# Generated by Django 5.0.2 on 2025-04-14 21:02

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="SteamAccount",
            fields=[
                (
                    "steam_id",
                    models.CharField(max_length=64, primary_key=True, serialize=False),
                ),
                ("auth_token", models.CharField(max_length=128, unique=True)),
                ("player_name", models.CharField(max_length=100)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="steam_accounts",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
    ]
