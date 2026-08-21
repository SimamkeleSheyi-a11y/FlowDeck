import uuid

from django.db import models

from apps.projects.models import Project

DEFAULT_COLUMN_NAMES = ["Backlog", "To Do", "In Progress", "Review", "Done"]
POSITION_GAP = 1000.0


class Board(models.Model):
    """
    One board per project (Phase 1 architecture doc's domain hierarchy:
    Project -> Board -> Columns -> Tasks). Created automatically alongside
    its project — see apps/boards/services.create_default_board(), called
    from ProjectListCreateView.post — never created directly by a client.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.OneToOneField(Project, on_delete=models.CASCADE, related_name="board")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Board for {self.project.name}"


class BoardColumn(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    board = models.ForeignKey(Board, on_delete=models.CASCADE, related_name="columns")
    name = models.CharField(max_length=50)

    # Explicit float position, not DB id, per the Phase 1 architecture doc's
    # "do not use database IDs as visual ordering" rule. Gap-based (steps of
    # POSITION_GAP) so inserting between two columns is a cheap midpoint
    # computation instead of renumbering every sibling.
    position = models.FloatField()

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["position"]
        constraints = [
            models.UniqueConstraint(fields=["board", "position"], name="uniq_col_pos_board"),
        ]

    def __str__(self):
        return f"{self.name} ({self.board_id})"
