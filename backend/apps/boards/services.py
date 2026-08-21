"""
Board/column business logic kept out of views.py: default-board creation
(called from the projects app when a project is created) and the position
math behind column reordering.
"""
from django.db import transaction

from .models import DEFAULT_COLUMN_NAMES, POSITION_GAP, Board, BoardColumn

# Below this gap, a float midpoint between two neighbors starts losing
# meaningful precision (repeatedly inserting in the same spot halves the
# gap each time, and IEEE-754 doubles run out of useful precision well
# before reaching true zero) — flagged as a known deferred risk in the
# Phase 1 architecture doc's risk table ("position field drift after many
# reorders"). MIN_GAP is generous headroom above actual float precision
# limits, not a hard IEEE-754 boundary.
MIN_GAP = 1e-6


def create_default_board(project) -> Board:
    """
    Called from apps.projects.views.ProjectListCreateView.post right after
    a project is created — every project gets a board with the standard
    five columns immediately, matching "each project gets a Kanban board"
    from the original spec. Never exposed as a client-facing endpoint.
    """
    with transaction.atomic():
        board = Board.objects.create(project=project)
        BoardColumn.objects.bulk_create(
            [
                BoardColumn(board=board, name=name, position=(index + 1) * POSITION_GAP)
                for index, name in enumerate(DEFAULT_COLUMN_NAMES)
            ]
        )
    return board


def next_append_position(board) -> float:
    """Position for a new column appended at the end of the board."""
    last = board.columns.order_by("-position").first()
    return (last.position + POSITION_GAP) if last else POSITION_GAP


def rebalance_columns(board, exclude_id=None) -> None:
    """
    Reassign clean, evenly-spaced positions while preserving current order.

    The (board, position) pair is unique. Updating rows directly from their
    old values to 1000, 2000, 3000, ... can therefore fail halfway through
    when a target position is still occupied by another row. Use a two-phase
    rewrite instead: move every column to a temporary range above all current
    positions, then assign the final clean positions to the non-moving
    siblings. If ``exclude_id`` is supplied, that row stays in the temporary
    range until the caller writes its newly computed position.
    """
    all_columns = list(board.columns.order_by("position", "created_at", "id"))
    if not all_columns:
        return

    columns = [column for column in all_columns if str(column.id) != str(exclude_id)]
    max_position = max(column.position for column in all_columns)
    temp_base = max_position + POSITION_GAP * (len(all_columns) + 2)

    with transaction.atomic():
        # Phase 1: vacate every existing position so final values cannot collide
        # with rows that have not yet been rewritten.
        for index, column in enumerate(all_columns):
            temporary_position = temp_base + (index + 1) * POSITION_GAP
            BoardColumn.objects.filter(id=column.id).update(position=temporary_position)

        # Phase 2: restore clean positions for all siblings participating in
        # the current ordering. The excluded/moving column remains temporary
        # and is updated by BoardColumnReorderView immediately afterwards.
        for index, column in enumerate(columns):
            BoardColumn.objects.filter(id=column.id).update(
                position=(index + 1) * POSITION_GAP
            )


def compute_reorder_position(board, after_column_id, moving_column_id=None) -> float:
    """
    Position for placing a column immediately after `after_column_id`
    within `board` (or first, if `after_column_id` is None) — a midpoint
    between its new neighbors so nothing else needs renumbering.
    `moving_column_id` is excluded from the neighbor lookup so a column
    doesn't collide with its own current position while being moved.

    If repeated inserts have narrowed the gap between two neighbors below
    MIN_GAP, rebalances the whole board first and recomputes — this keeps
    the gap-based scheme workable indefinitely instead of degrading after
    enough reorders land in the same spot.
    """
    siblings = list(board.columns.exclude(id=moving_column_id).order_by("position"))

    if after_column_id is None:
        following = siblings[0] if siblings else None
        return (following.position - POSITION_GAP) if following else POSITION_GAP

    after_index = next((i for i, c in enumerate(siblings) if str(c.id) == str(after_column_id)), None)
    if after_index is None:
        raise ValueError("after_column_id is not a column on this board")

    after_column = siblings[after_index]
    following = siblings[after_index + 1] if after_index + 1 < len(siblings) else None
    if following is None:
        return after_column.position + POSITION_GAP

    if following.position - after_column.position < MIN_GAP:
        rebalance_columns(board, exclude_id=moving_column_id)
        return compute_reorder_position(board, after_column_id, moving_column_id=moving_column_id)

    return (after_column.position + following.position) / 2
