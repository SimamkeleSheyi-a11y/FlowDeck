import uuid

from django.conf import settings
from django.db import models

from apps.projects.models import Project
from apps.tasks.models import Task
from apps.workspaces.models import Workspace


class ActivityEventType(models.TextChoices):
    """
    Phase 1 architecture doc, Section 5.4. A plain CharField with choices —
    adding a new choice here is a Python-level change only (no DB
    constraint enforces the set), so extending this list later never needs
    a migration.
    """

    WORKSPACE_CREATED = "WORKSPACE_CREATED", "Workspace created"
    WORKSPACE_MEMBER_JOINED = "WORKSPACE_MEMBER_JOINED", "Workspace member joined"
    WORKSPACE_MEMBER_ROLE_CHANGED = "WORKSPACE_MEMBER_ROLE_CHANGED", "Workspace member role changed"
    WORKSPACE_MEMBER_REMOVED = "WORKSPACE_MEMBER_REMOVED", "Workspace member removed"
    WORKSPACE_OWNERSHIP_TRANSFERRED = "WORKSPACE_OWNERSHIP_TRANSFERRED", "Workspace ownership transferred"

    PROJECT_CREATED = "PROJECT_CREATED", "Project created"
    PROJECT_MEMBER_ADDED = "PROJECT_MEMBER_ADDED", "Project member added"
    PROJECT_MEMBER_REMOVED = "PROJECT_MEMBER_REMOVED", "Project member removed"

    TASK_CREATED = "TASK_CREATED", "Task created"
    TASK_UPDATED = "TASK_UPDATED", "Task updated"
    TASK_MOVED = "TASK_MOVED", "Task moved"
    TASK_DELETED = "TASK_DELETED", "Task deleted"
    TASK_COMPLETED = "TASK_COMPLETED", "Task completed"
    TASK_REOPENED = "TASK_REOPENED", "Task reopened"
    TASK_ASSIGNED = "TASK_ASSIGNED", "Task assigned"
    TASK_UNASSIGNED = "TASK_UNASSIGNED", "Task unassigned"
    TASK_PRIORITY_CHANGED = "TASK_PRIORITY_CHANGED", "Priority changed"
    TASK_DUE_DATE_CHANGED = "TASK_DUE_DATE_CHANGED", "Due date changed"

    COMMENT_ADDED = "COMMENT_ADDED", "Comment added"
    COMMENT_EDITED = "COMMENT_EDITED", "Comment edited"
    COMMENT_DELETED = "COMMENT_DELETED", "Comment deleted"

    CHECKLIST_ITEM_ADDED = "CHECKLIST_ITEM_ADDED", "Checklist item added"
    CHECKLIST_ITEM_COMPLETED = "CHECKLIST_ITEM_COMPLETED", "Checklist item completed"

    LABEL_ADDED = "LABEL_ADDED", "Label added"
    LABEL_REMOVED = "LABEL_REMOVED", "Label removed"


class ActivityEvent(models.Model):
    """
    Server-authoritative audit trail — every row here is written by a view
    after a mutation succeeds, never accepted as input from a client
    (Phase 1 doc, Section 8: "never trust the frontend to generate
    authoritative history").

    workspace/project/task use on_delete=SET_NULL rather than CASCADE
    deliberately: deleting a task/project/workspace must not delete the
    historical record that it ever existed or what happened to it (Phase 1
    doc, Section 16: "do not blindly cascade-delete important historical
    records"). target_type/target_id are a soft (non-FK) reference to
    whatever specific object the event is about (a comment, a label, a
    checklist item) — those don't get their own FK here, keeping this
    model's hard dependencies limited to the three scoping dimensions
    (workspace/project/task) that every event actually has.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+")
    event_type = models.CharField(max_length=40, choices=ActivityEventType.choices)

    target_type = models.CharField(max_length=30, blank=True, default="")
    target_id = models.UUIDField(null=True, blank=True)

    workspace = models.ForeignKey(Workspace, on_delete=models.SET_NULL, null=True, related_name="+")
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True, related_name="+")
    task = models.ForeignKey(Task, on_delete=models.SET_NULL, null=True, related_name="activity_events")

    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["task", "created_at"], name="activity_ae_task_created_idx"),
            models.Index(fields=["project", "created_at"], name="act_project_created_idx"),
        ]

    def __str__(self):
        return f"{self.event_type} @ {self.created_at:%Y-%m-%d %H:%M}"
