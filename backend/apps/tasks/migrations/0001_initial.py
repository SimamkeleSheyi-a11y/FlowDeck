import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    """
    HAND-AUTHORED, NOT MACHINE-GENERATED — see
    apps/users/migrations/0001_initial.py for the full explanation. Run
    `python manage.py makemigrations --check --dry-run` once you can to
    confirm this matches the real autodetector's output. Every index below
    has an explicit `name=` matching models.py exactly (the fix applied
    after the Phase 3 index-rename issue), applied here from the start.
    """

    initial = True

    dependencies = [
        ("boards", "0001_initial"),
        ("projects", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Task",
            fields=[
                (
                    "id",
                    models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False),
                ),
                ("title", models.CharField(max_length=200)),
                ("description", models.TextField(blank=True, default="")),
                (
                    "priority",
                    models.CharField(
                        choices=[
                            ("LOW", "Low"),
                            ("MEDIUM", "Medium"),
                            ("HIGH", "High"),
                            ("URGENT", "Urgent"),
                        ],
                        default="MEDIUM",
                        max_length=10,
                    ),
                ),
                ("position", models.FloatField()),
                ("start_date", models.DateField(blank=True, null=True)),
                ("due_date", models.DateField(blank=True, null=True)),
                ("is_completed", models.BooleanField(default=False)),
                ("version", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "column",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="tasks",
                        to="boards.boardcolumn",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "project",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="tasks",
                        to="projects.project",
                    ),
                ),
            ],
            options={"ordering": ["position"]},
        ),
        migrations.AddIndex(
            model_name="task",
            index=models.Index(fields=["project", "is_completed"], name="tasks_task_proj_done_idx"),
        ),
        migrations.AddIndex(
            model_name="task",
            index=models.Index(fields=["due_date"], name="tasks_task_due_date_idx"),
        ),
    ]
