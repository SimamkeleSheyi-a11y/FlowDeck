import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    """
    HAND-AUTHORED, NOT MACHINE-GENERATED — see
    apps/users/migrations/0001_initial.py for the full explanation. Run
    `python manage.py makemigrations --check --dry-run` to confirm this
    matches the real autodetector's output. Every index has an explicit
    `name=` matching models.py exactly, same discipline as every migration
    since the Phase 3 index-rename fix.
    """

    initial = True

    dependencies = [
        ("workspaces", "0001_initial"),
        ("projects", "0001_initial"),
        ("tasks", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ActivityEvent",
            fields=[
                (
                    "id",
                    models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False),
                ),
                (
                    "event_type",
                    models.CharField(
                        choices=[
                            ("WORKSPACE_CREATED", "Workspace created"),
                            ("WORKSPACE_MEMBER_JOINED", "Workspace member joined"),
                            ("WORKSPACE_MEMBER_ROLE_CHANGED", "Workspace member role changed"),
                            ("WORKSPACE_MEMBER_REMOVED", "Workspace member removed"),
                            ("WORKSPACE_OWNERSHIP_TRANSFERRED", "Workspace ownership transferred"),
                            ("PROJECT_CREATED", "Project created"),
                            ("PROJECT_MEMBER_ADDED", "Project member added"),
                            ("PROJECT_MEMBER_REMOVED", "Project member removed"),
                            ("TASK_CREATED", "Task created"),
                            ("TASK_UPDATED", "Task updated"),
                            ("TASK_MOVED", "Task moved"),
                            ("TASK_DELETED", "Task deleted"),
                            ("TASK_COMPLETED", "Task completed"),
                            ("TASK_REOPENED", "Task reopened"),
                            ("TASK_ASSIGNED", "Task assigned"),
                            ("TASK_UNASSIGNED", "Task unassigned"),
                            ("TASK_PRIORITY_CHANGED", "Priority changed"),
                            ("TASK_DUE_DATE_CHANGED", "Due date changed"),
                            ("COMMENT_ADDED", "Comment added"),
                            ("COMMENT_EDITED", "Comment edited"),
                            ("COMMENT_DELETED", "Comment deleted"),
                            ("CHECKLIST_ITEM_ADDED", "Checklist item added"),
                            ("CHECKLIST_ITEM_COMPLETED", "Checklist item completed"),
                            ("LABEL_ADDED", "Label added"),
                            ("LABEL_REMOVED", "Label removed"),
                        ],
                        max_length=40,
                    ),
                ),
                ("target_type", models.CharField(blank=True, default="", max_length=30)),
                ("target_id", models.UUIDField(blank=True, null=True)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "actor",
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
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to="workspaces.workspace",
                    ),
                ),
                (
                    "project",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to="projects.project",
                    ),
                ),
                (
                    "task",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="activity_events",
                        to="tasks.task",
                    ),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.AddIndex(
            model_name="activityevent",
            index=models.Index(fields=["task", "created_at"], name="activity_ae_task_created_idx"),
        ),
        migrations.AddIndex(
            model_name="activityevent",
            index=models.Index(fields=["project", "created_at"], name="act_project_created_idx"),
        ),
    ]
