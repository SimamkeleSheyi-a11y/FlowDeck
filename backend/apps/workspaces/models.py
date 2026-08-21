import hashlib
import uuid
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.text import slugify


class Workspace(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    description = models.CharField(max_length=280, blank=True, default="")

    # Historical only — who originally created the workspace. This is NOT
    # the current owner and must never be read to determine ownership or
    # permissions; the single source of truth for that is the
    # WorkspaceMembership row with role=OWNER (see that model's docstring
    # and the unique_workspace_owner constraint below). Phase 1 architecture
    # doc, Section 5.1.
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    archived_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = self._generate_unique_slug()
        super().save(*args, **kwargs)

    def _generate_unique_slug(self):
        base = slugify(self.name)[:100] or "workspace"
        slug = base
        suffix = 1
        while Workspace.objects.filter(slug=slug).exists():
            suffix += 1
            slug = f"{base}-{suffix}"
        return slug


class WorkspaceRole(models.TextChoices):
    OWNER = "OWNER", "Owner"
    ADMIN = "ADMIN", "Admin"
    MEMBER = "MEMBER", "Member"


class WorkspaceMembership(models.Model):
    """
    The single source of truth for who owns a workspace is the row here
    with role=OWNER — NOT any field on Workspace itself (Phase 1 architecture
    doc, Section 5.1, correction #4). The unique_workspace_owner constraint
    below enforces "at most one OWNER row per workspace" at the database
    level via a partial unique index (supported on Postgres and SQLite).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="workspace_memberships"
    )
    role = models.CharField(max_length=10, choices=WorkspaceRole.choices)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["workspace", "user"], name="unique_workspace_membership"),
            models.UniqueConstraint(
                fields=["workspace"],
                condition=models.Q(role="OWNER"),
                name="unique_workspace_owner",
            ),
        ]
        indexes = [models.Index(fields=["workspace", "role"], name="workspaces_wm_ws_role_idx")]

    def __str__(self):
        return f"{self.user_id} @ {self.workspace_id} ({self.role})"


class InvitationRole(models.TextChoices):
    # Deliberately excludes OWNER — ownership never travels through an
    # invitation, only through the dedicated transfer endpoint.
    ADMIN = "ADMIN", "Admin"
    MEMBER = "MEMBER", "Member"


class InvitationStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    ACCEPTED = "ACCEPTED", "Accepted"
    REVOKED = "REVOKED", "Revoked"
    EXPIRED = "EXPIRED", "Expired"


def default_invitation_expiry():
    return timezone.now() + timedelta(days=7)


class WorkspaceInvitation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="invitations")
    email = models.EmailField()
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )
    intended_role = models.CharField(max_length=10, choices=InvitationRole.choices, default=InvitationRole.MEMBER)
    status = models.CharField(max_length=10, choices=InvitationStatus.choices, default=InvitationStatus.PENDING)

    # Only a SHA-256 hash of the invitation token is ever stored — same
    # treatment as password-reset tokens. The raw token exists only in the
    # outbound email link and is never persisted anywhere. unique=True gives
    # a direct indexed lookup (see services.resolve_invitation_by_raw_token)
    # instead of scanning every pending invitation.
    token_hash = models.CharField(max_length=64, unique=True, editable=False)
    expires_at = models.DateTimeField(default=default_invitation_expiry)

    created_at = models.DateTimeField(auto_now_add=True)
    responded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["workspace", "email"],
                condition=models.Q(status="PENDING"),
                name="uniq_pending_invite_email",
            ),
        ]

    def __str__(self):
        return f"{self.email} -> {self.workspace_id} ({self.status})"

    @property
    def is_expired(self) -> bool:
        return timezone.now() >= self.expires_at

    @staticmethod
    def hash_token(raw_token: str) -> str:
        return hashlib.sha256(raw_token.encode()).hexdigest()

    def set_token(self, raw_token: str) -> None:
        self.token_hash = self.hash_token(raw_token)
