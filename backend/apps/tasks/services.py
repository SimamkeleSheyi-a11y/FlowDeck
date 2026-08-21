"""Position math for placing/moving tasks within a column — same gap-based
scheme and same shape as apps.boards.services' column reorder helpers,
scoped to a column's tasks instead of a board's columns. Also the checklist
lazy-creation helper used by the Phase 6 checklist endpoints, and the
Phase 8 rebalancing helpers for both tasks and checklist items."""
from .models import POSITION_GAP, Checklist, ChecklistItem, Task

# Same rationale and threshold as apps.boards.services.MIN_GAP — flagged as
# a known deferred risk in the Phase 1 architecture doc's risk table
# ("position field drift after many reorders").
MIN_GAP = 1e-6


def next_append_position(column) -> float:
    last = column.tasks.order_by("-position").first()
    return (last.position + POSITION_GAP) if last else POSITION_GAP


def rebalance_tasks(column, exclude_id=None) -> None:
    """Reassigns clean, evenly-spaced positions to every task in a column,
    preserving current order — self-healing counterpart to position drift,
    same shape as apps.boards.services.rebalance_columns."""
    tasks = list(column.tasks.exclude(id=exclude_id).order_by("position"))
    for index, task in enumerate(tasks):
        new_position = (index + 1) * POSITION_GAP
        if task.position != new_position:
            Task.objects.filter(id=task.id).update(position=new_position)


def compute_move_position(column, after_task_id, moving_task_id=None) -> float:
    """
    If repeated inserts have narrowed the gap between two neighbors below
    MIN_GAP, rebalances the column's tasks first and recomputes — see
    apps.boards.services.compute_reorder_position for the full rationale.
    """
    siblings = list(column.tasks.exclude(id=moving_task_id).order_by("position"))

    if after_task_id is None:
        following = siblings[0] if siblings else None
        return (following.position - POSITION_GAP) if following else POSITION_GAP

    after_index = next((i for i, t in enumerate(siblings) if str(t.id) == str(after_task_id)), None)
    if after_index is None:
        raise ValueError("after_task_id is not a task in this column")

    after_task = siblings[after_index]
    following = siblings[after_index + 1] if after_index + 1 < len(siblings) else None
    if following is None:
        return after_task.position + POSITION_GAP

    if following.position - after_task.position < MIN_GAP:
        rebalance_tasks(column, exclude_id=moving_task_id)
        return compute_move_position(column, after_task_id, moving_task_id=moving_task_id)

    return (after_task.position + following.position) / 2


def get_or_create_checklist(task) -> Checklist:
    """A task's checklist is created lazily on first touch (GET or POST to
    /tasks/{id}/checklist/) rather than requiring a separate creation step
    — matches the singular, always-there-conceptually shape implied by the
    Phase 1 API map's `/tasks/{id}/checklist/` (not `/checklists/`)."""
    checklist, _created = Checklist.objects.get_or_create(task=task)
    return checklist


def next_checklist_item_position(checklist) -> float:
    last = checklist.items.order_by("-position").first()
    return (last.position + POSITION_GAP) if last else POSITION_GAP


def rebalance_checklist_items(checklist, exclude_id=None) -> None:
    """Same rebalancing shape as rebalance_tasks/rebalance_columns, scoped
    to one checklist's items."""
    items = list(checklist.items.exclude(id=exclude_id).order_by("position"))
    for index, item in enumerate(items):
        new_position = (index + 1) * POSITION_GAP
        if item.position != new_position:
            ChecklistItem.objects.filter(id=item.id).update(position=new_position)


def compute_checklist_item_position(checklist, after_item_id, moving_item_id=None) -> float:
    """
    Same gap-based midpoint scheme as compute_move_position (tasks) and
    compute_reorder_position (columns). Siblings are scoped to
    `checklist.items` only, so an after_item_id from a different checklist
    simply won't be found (ValueError) — there's no parameter anywhere in
    this call chain that names a *different* checklist to move into, so
    cross-task/cross-project movement isn't just rejected, it's not an
    expressible request in the first place.

    Rebalances first (see compute_move_position) if repeated inserts have
    narrowed a gap below MIN_GAP.
    """
    siblings = list(checklist.items.exclude(id=moving_item_id).order_by("position"))

    if after_item_id is None:
        following = siblings[0] if siblings else None
        return (following.position - POSITION_GAP) if following else POSITION_GAP

    after_index = next((i for i, it in enumerate(siblings) if str(it.id) == str(after_item_id)), None)
    if after_index is None:
        raise ValueError("after_item_id is not an item in this checklist")

    after_item = siblings[after_index]
    following = siblings[after_index + 1] if after_index + 1 < len(siblings) else None
    if following is None:
        return after_item.position + POSITION_GAP

    if following.position - after_item.position < MIN_GAP:
        rebalance_checklist_items(checklist, exclude_id=moving_item_id)
        return compute_checklist_item_position(checklist, after_item_id, moving_item_id=moving_item_id)

    return (after_item.position + following.position) / 2
