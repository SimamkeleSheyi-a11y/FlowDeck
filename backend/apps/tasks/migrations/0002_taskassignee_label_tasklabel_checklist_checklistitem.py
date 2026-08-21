import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    """
    HAND-AUTHORED, NOT MACHINE-GENERATED — see
    apps/users/migrations/0001_initial.py for the full explanation. A
    follow-up migration rather than folding into 0001_initial: unlike the
    earlier apps, this one might already have 0001 applied against a real
    database by now, so Phase 6 additions go in their own migration the way
    a real `makemigrations` run would produce. Run
    `python manage.py makemigrations --check --dry-run` to confirm.
    """

    dependencies = [
        ("tasks", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Label",
            fields=[
                (
                    "id",
                    models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False),
                ),
                ("name", models.CharField(max_length=40)),
                ("color", models.CharField(default="#6B7280", max_length=7)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "project",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="labels",
                        to="projects.project",
                    ),
                ),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="TaskAssignee",
            fields=[
                (
                    "id",
                    models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False),
                ),
                ("assigned_at", models.DateTimeField(auto_now_add=True)),
                (
                    "assigned_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "task",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="assignees",
                        to="tasks.task",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="task_assignments",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="TaskLabel",
            fields=[
                (
                    "id",
                    models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False),
                ),
                ("added_at", models.DateTimeField(auto_now_add=True)),
                (
                    "label",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="task_labels",
                        to="tasks.label",
                    ),
                ),
                (
                    "task",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="task_labels",
                        to="tasks.task",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="Checklist",
            fields=[
                (
                    "id",
                    models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "task",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="checklist",
                        to="tasks.task",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="ChecklistItem",
            fields=[
                (
                    "id",
                    models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False),
                ),
                ("text", models.CharField(max_length=280)),
                ("is_done", models.BooleanField(default=False)),
                ("position", models.FloatField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "checklist",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="items",
                        to="tasks.checklist",
                    ),
                ),
            ],
            options={"ordering": ["position"]},
        ),
        migrations.AddConstraint(
            model_name="label",
            constraint=models.UniqueConstraint(
                fields=["project", "name"], name="unique_label_name_per_project"
            ),
        ),
        migrations.AddConstraint(
            model_name="taskassignee",
            constraint=models.UniqueConstraint(fields=["task", "user"], name="unique_task_assignee"),
        ),
        migrations.AddConstraint(
            model_name="tasklabel",
            constraint=models.UniqueConstraint(fields=["task", "label"], name="unique_task_label"),
        ),
    ]
