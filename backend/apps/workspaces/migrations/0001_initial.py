import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

import apps.workspaces.models


class Migration(migrations.Migration):
    """
    HAND-AUTHORED, NOT MACHINE-GENERATED — see apps/users/migrations/0001_initial.py
    for the full explanation. Run `python manage.py makemigrations --check
    --dry-run` once Django is actually installed to confirm this matches
    what the real autodetector would produce.

    Includes the token_hash uniqueness fix from the Phase 3 corrections
    directly in this initial migration rather than as a follow-up migration,
    since nothing has ever actually been deployed against the earlier
    (non-unique) version of this field.
    """

    initial = True

    dependencies = [
        ("users", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Workspace",
            fields=[
                (
                    "id",
                    models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False),
                ),
                ("name", models.CharField(max_length=100)),
                ("slug", models.SlugField(blank=True, max_length=120, unique=True)),
                ("description", models.CharField(blank=True, default="", max_length=280)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("archived_at", models.DateTimeField(blank=True, null=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="WorkspaceMembership",
            fields=[
                (
                    "id",
                    models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False),
                ),
                (
                    "role",
                    models.CharField(
                        choices=[("OWNER", "Owner"), ("ADMIN", "Admin"), ("MEMBER", "Member")],
                        max_length=10,
                    ),
                ),
                ("joined_at", models.DateTimeField(auto_now_add=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="workspace_memberships",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "workspace",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="memberships",
                        to="workspaces.workspace",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="WorkspaceInvitation",
            fields=[
                (
                    "id",
                    models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False),
                ),
                ("email", models.EmailField(max_length=254)),
                (
                    "intended_role",
                    models.CharField(
                        choices=[("ADMIN", "Admin"), ("MEMBER", "Member")],
                        default="MEMBER",
                        max_length=10,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("PENDING", "Pending"),
                            ("ACCEPTED", "Accepted"),
                            ("REVOKED", "Revoked"),
                            ("EXPIRED", "Expired"),
                        ],
                        default="PENDING",
                        max_length=10,
                    ),
                ),
                ("token_hash", models.CharField(editable=False, max_length=64, unique=True)),
                (
                    "expires_at",
                    models.DateTimeField(default=apps.workspaces.models.default_invitation_expiry),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("responded_at", models.DateTimeField(blank=True, null=True)),
                (
                    "invited_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "workspace",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="invitations",
                        to="workspaces.workspace",
                    ),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.AddIndex(
            model_name="workspacemembership",
            index=models.Index(fields=["workspace", "role"], name="workspaces_wm_ws_role_idx"),
        ),
        migrations.AddConstraint(
            model_name="workspacemembership",
            constraint=models.UniqueConstraint(fields=["workspace", "user"], name="unique_workspace_membership"),
        ),
        migrations.AddConstraint(
            model_name="workspacemembership",
            constraint=models.UniqueConstraint(
                condition=models.Q(role="OWNER"),
                fields=["workspace"],
                name="unique_workspace_owner",
            ),
        ),
        migrations.AddConstraint(
            model_name="workspaceinvitation",
            constraint=models.UniqueConstraint(
                condition=models.Q(status="PENDING"),
                fields=["workspace", "email"],
                name="uniq_pending_invite_email",
            ),
        ),
    ]
