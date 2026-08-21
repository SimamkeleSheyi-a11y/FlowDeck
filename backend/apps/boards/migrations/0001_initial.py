import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """
    HAND-AUTHORED, NOT MACHINE-GENERATED — see
    apps/users/migrations/0001_initial.py for the full explanation. Run
    `python manage.py makemigrations --check --dry-run` once you can to
    confirm this matches what the real autodetector produces. Every
    `models.Index`/`models.UniqueConstraint` below has an explicit `name=`
    matching models.py exactly, which is what fixed the index-rename issue
    found in apps/{users,workspaces,projects} — same approach applied here
    from the start rather than needing a follow-up correction.
    """

    initial = True

    dependencies = [
        ("projects", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Board",
            fields=[
                (
                    "id",
                    models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "project",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="board",
                        to="projects.project",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="BoardColumn",
            fields=[
                (
                    "id",
                    models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False),
                ),
                ("name", models.CharField(max_length=50)),
                ("position", models.FloatField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "board",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="columns",
                        to="boards.board",
                    ),
                ),
            ],
            options={"ordering": ["position"]},
        ),
        migrations.AddConstraint(
            model_name="boardcolumn",
            constraint=models.UniqueConstraint(
                fields=["board", "position"], name="uniq_col_pos_board"
            ),
        ),
    ]
