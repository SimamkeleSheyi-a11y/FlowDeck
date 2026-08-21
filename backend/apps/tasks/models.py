import uuid

from django.conf import settings
from django.db import models

from apps.boards.models import BoardColumn
from apps.projects.models import Project

POSITION_GAP = 1000.0


class TaskPriority(models.TextChoices):
    LOW = "LOW", "Low"
    MEDIUM = "MEDIUM", "Medium"
    HIGH = "HIGH", "High"
    URGENT = "URGENT", "Urgent"


class Task(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    column = models.ForeignKey(BoardColumn, on_delete=models.CASCADE, related_name="tasks")

    # Denormalized from column.board.project for query speed (Phase 1
    # architecture doc, Section 5) — always equal to column.board.project;
    # kept in sync at creation and never changed independently (a task can
    # only move between columns on its own project's board — enforced in
    # TaskMoveView by scoping the target column lookup to task.project).
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="tasks")

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, default="")
    priority = models.CharField(max_length=10, choices=TaskPriority.choices, default=TaskPriority.MEDIUM)

    # Explicit float position within its column, gap-based — same scheme as
    # BoardColumn.position (Phase 1 doc: "do not use database IDs as visual
    # ordering").
    position = models.FloatField()

    start_date = models.DateField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    is_completed = models.BooleanField(default=False)

    # Optimistic-concurrency counter (Phase 1 architecture doc, Section 5.3).
    # Incremented on every mutating write. TaskMoveView compares the
    # client's submitted version against this and flags (not rejects) a
    # mismatch for the Phase 5/8 MVP — see that view's docstring.
    version = models.PositiveIntegerField(default=0)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["position"]
        indexes = [
            models.Index(fields=["project", "is_completed"], name="tasks_task_proj_done_idx"),
            models.Index(fields=["due_date"], name="tasks_task_due_date_idx"),
        ]

    def __str__(self):
        return self.title


class TaskAssignee(models.Model):
    """Multiple assignees per task. Who may be assigned is enforced at the
    view layer (apps.tasks.views): a target user must have project access
    per Section 6.1, matching "prevent assigning users who are not members
    of the appropriate workspace/project" from the original spec."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="assignees")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="task_assignments"
    )
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["task", "user"], name="unique_task_assignee")]

    def __str__(self):
        return f"{self.user_id} -> {self.task_id}"


class Label(models.Model):
    """Project-scoped tag vocabulary — a label belongs to one project and
    can be attached to any task within it (TaskLabel, below)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="labels")
    name = models.CharField(max_length=40)
    color = models.CharField(max_length=7, default="#6B7280")  # hex, e.g. "#EF4444"

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["project", "name"], name="unique_label_name_per_project"),
        ]

    def __str__(self):
        return f"{self.name} ({self.project_id})"


class TaskLabel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="task_labels")
    label = models.ForeignKey(Label, on_delete=models.CASCADE, related_name="task_labels")
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["task", "label"], name="unique_task_label")]

    def __str__(self):
        return f"{self.label_id} on {self.task_id}"


class Checklist(models.Model):
    """
    One checklist per task (Phase 1 API map: singular `/tasks/{id}/checklist/`).
    Created lazily — see apps.tasks.services.get_or_create_checklist — not
    directly by the client.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task = models.OneToOneField(Task, on_delete=models.CASCADE, related_name="checklist")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Checklist for {self.task_id}"


class ChecklistItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    checklist = models.ForeignKey(Checklist, on_delete=models.CASCADE, related_name="items")
    text = models.CharField(max_length=280)
    is_done = models.BooleanField(default=False)
    position = models.FloatField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["position"]

    def __str__(self):
        return self.text
