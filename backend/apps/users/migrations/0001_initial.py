import uuid

from django.db import migrations, models

import apps.users.managers
import apps.users.models


class Migration(migrations.Migration):
    """
    HAND-AUTHORED, NOT MACHINE-GENERATED.

    This sandbox has no Django installed and no network access to install
    it, so `python manage.py makemigrations` could not actually be run. This
    file is my best-effort reconstruction of what it would produce for the
    User model in apps/users/models.py as of Phase 3.

    It should be functionally correct — creating it against a fresh database
    will produce the right tables, columns, and constraints — but exact
    cosmetic details (field ordering, auto-generated index names) may not
    byte-for-byte match real makemigrations output. Before relying on this:

        python manage.py makemigrations --check --dry-run

    If Django reports no changes needed, this file is confirmed correct. If
    it wants to add something, that's real signal to fix — trust Django's
    autodetector over this file for anything they disagree on.
    """

    initial = True

    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.CreateModel(
            name="User",
            fields=[
                (
                    "id",
                    models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False),
                ),
                ("password", models.CharField(max_length=128, verbose_name="password")),
                ("last_login", models.DateTimeField(blank=True, null=True, verbose_name="last login")),
                (
                    "is_superuser",
                    models.BooleanField(
                        default=False,
                        help_text=(
                            "Designates that this user has all permissions without "
                            "explicitly assigning them."
                        ),
                        verbose_name="superuser status",
                    ),
                ),
                (
                    "email",
                    models.EmailField(
                        db_index=True, max_length=254, unique=True, verbose_name="email address"
                    ),
                ),
                ("display_name", models.CharField(max_length=100)),
                ("bio", models.CharField(blank=True, default="", max_length=280)),
                (
                    "avatar",
                    models.ImageField(
                        blank=True, null=True, upload_to=apps.users.models.avatar_upload_path
                    ),
                ),
                ("is_email_verified", models.BooleanField(default=False)),
                ("is_active", models.BooleanField(default=True)),
                ("is_staff", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "groups",
                    models.ManyToManyField(
                        blank=True,
                        help_text=(
                            "The groups this user belongs to. A user will get all "
                            "permissions granted to each of their groups."
                        ),
                        related_name="user_set",
                        related_query_name="user",
                        to="auth.group",
                        verbose_name="groups",
                    ),
                ),
                (
                    "user_permissions",
                    models.ManyToManyField(
                        blank=True,
                        help_text="Specific permissions for this user.",
                        related_name="user_set",
                        related_query_name="user",
                        to="auth.permission",
                        verbose_name="user permissions",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
            managers=[
                ("objects", apps.users.managers.UserManager()),
            ],
        ),
        migrations.AddIndex(
            model_name="user",
            index=models.Index(fields=["email"], name="users_user_email_idx"),
        ),
    ]
