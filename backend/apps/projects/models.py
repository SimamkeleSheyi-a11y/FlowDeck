import uuid

from django.conf import settings
from django.db import models

from apps.workspaces.models import Workspace


class Project(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="projects")
    name = models.CharField(max_length=100)
    description = models.CharField(max_length=500, blank=True, default="")

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    archived_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["workspace", "archived_at"], name="projects_ws_archived_idx")]

    def __str__(self):
        return self.name


class ProjectMembership(models.Model):
    """
    Binary membership only — no role field on purpose (Phase 1 architecture
    doc, Section 5.2 / correction #3). Permission *level* always comes from
    the user's workspace-wide role (OWNER/ADMIN/MEMBER); this table only
    controls which specific projects a workspace MEMBER can see and act on.

    OWNER and ADMIN have implicit access to every project in their
    workspace whether or not a row exists here for them — see the explicit
    rule in Section 6.1 and apps/projects/permissions.py, which is the only
    place that rule is implemented.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="project_memberships"
    )
    added_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["project", "user"], name="unique_project_membership"),
        ]
        indexes = [models.Index(fields=["project"], name="projects_pm_project_idx")]

    def __str__(self):
        return f"{self.user_id} @ {self.project_id}"
