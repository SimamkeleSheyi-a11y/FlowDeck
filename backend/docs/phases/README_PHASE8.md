# FlowDeck Backend — Phase 8: Drag-and-Drop Boards

Built on the accepted Phase 7 baseline. Three features, exactly as scoped
and approved: a full board state endpoint, position rebalancing (columns,
tasks, checklist items), and opt-in strict conflict handling on task move.

## Execution status — unchanged

Still no Django, no network to install it here. Test count computed from
source, not from a run:

- **211 test functions** (195 preserved + 16 new)
- **220 test cases** — the pre-existing parametrized permission-matrix
  tests still add +9 beyond their function count, same gap as every round
  since Phase 6. `pytest -v` will report 220 collected.

Exact commands, unchanged:

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python manage.py makemigrations --check --dry-run
python manage.py migrate
python manage.py check
pytest -v
```

## Migration summary: none needed

**No new migration, nothing modified or squashed.** All three Phase 8
features are pure application-logic additions — new serializers/views
reusing existing model fields (`BoardFullView` nests already-existing
data), rebalancing rewrites existing `position` float values (no schema
change), and `strict` is a request-body field on a plain
`serializers.Serializer`, not a model field. Migration directory listing
is byte-for-byte identical to the accepted Phase 7 baseline — same 8
files, same content.

## 1. Full board state endpoint

`GET /api/boards/{board_id}/full/` — columns in position order, each with
its tasks in position order, each task carrying the same fields
`TaskSerializer` already exposes elsewhere (assignees, labels, checklist
totals/done counts, priority, dates, version). N+1-safe: one query for the
board+columns (`Prefetch("columns", ...)`), one for all tasks across those
columns (`Prefetch("columns__tasks", ...)` via a nested queryset), and
`Prefetch`+`annotate` for assignees/labels/checklist counts inside that —
same pattern already used for the plain task list endpoint since Phase 6,
now nested one level deeper. Verified with
`django_assert_max_num_queries(20)` while creating 10 extra tasks across
columns in the same test.

**`GET /api/boards/{id}/` is completely untouched** — new
`BoardColumnWithTasksSerializer`/`BoardWithTasksSerializer` are separate
from the existing `BoardColumnSerializer`/`BoardSerializer`, used only by
the new endpoint. `test_existing_board_detail_endpoint_unchanged_by_full_endpoint`
checks the old endpoint's response has no `tasks` key at all.

Enforces the same project-visibility rule as every other board/task
endpoint (`visible_boards_for_user`, 404-not-403 for non-members).

## 2. Position rebalancing

Every gap-based position scheme in the app (`apps.boards.services` for
columns, `apps.tasks.services` for tasks and checklist items) now checks,
on the "insert between two full neighbors" path: if the gap between the
two neighbors is below `MIN_GAP` (`1e-6` — generous headroom above actual
float-precision limits), rebalance every sibling to fresh evenly-spaced
positions (multiples of `POSITION_GAP`) first, then recompute the
insertion. Self-healing — nothing needs to notice drift and call it
explicitly; it happens transparently the next time an insert would
otherwise collide.

Two tests per scope (columns, tasks, checklist items — six total):
- A **direct-trigger** test: manually sets two adjacent siblings' gap
  below `MIN_GAP` via the ORM, confirms the next insert succeeds, and
  confirms every position afterward is distinct with healthy gaps.
- A **repeated-operations** test: 40 real, sequential reorder/move calls
  through the actual endpoints (not simulated), each inserted right after
  the same anchor — which keeps halving that specific gap, comfortably
  exhausting the ~30 halvings needed to go from `POSITION_GAP` (1000.0)
  past `MIN_GAP`. Every one of the 40 calls must return `200`; final
  assertion confirms no duplicate positions and a still-correctly-ordered
  sequence.

## 3. Strict task-move conflict handling

`TaskMoveSerializer` gained `strict` (boolean, default `False`).
`TaskMoveView`: when `strict=true` and the submitted `version` doesn't
match the task's current version, returns `409 CONFLICT` with
`{"code": "version_conflict", "current": <canonical task state>}` —
checked *before* any mutation, so the task's column/position/version are
completely untouched and no `TASK_MOVED` activity event is logged.

When `strict` is omitted or `false`, behavior is byte-for-byte the
original Phase 5 accept-and-flag path — verified by two regression tests
that replay the exact stale-version scenario from Phase 5's own test
(`test_move_with_stale_version_still_applies_but_flags_conflict`) without
`strict`, confirming the move still applies and `conflict: true` still
surfaces exactly as before.

## Files changed

```
apps/boards/services.py        rebalance_columns() + MIN_GAP-aware compute_reorder_position
apps/boards/serializers.py       +BoardColumnWithTasksSerializer, +BoardWithTasksSerializer
apps/boards/views.py               +BoardFullView
apps/boards/urls.py                 +1 route
apps/tasks/services.py               rebalance_tasks()/rebalance_checklist_items() +
                                       MIN_GAP-aware compute_move_position/
                                       compute_checklist_item_position
apps/tasks/serializers.py              TaskMoveSerializer +strict field
apps/tasks/views.py                     TaskMoveView strict-mode branch + docstring update
apps/boards/tests/test_board_full.py           new — 6 tests
apps/boards/tests/test_position_rebalancing.py   new — 2 tests
apps/tasks/tests/test_position_rebalancing.py      new — 4 tests
apps/tasks/tests/test_task_move_strict.py            new — 4 tests
```

Not touched: every migration, every existing test file, every model, and
every other view across all seven prior phases. No permission check was
loosened anywhere — the full board endpoint enforces the identical
visibility rule as the plain board endpoint; strict mode only ever adds a
new way to *reject* a stale move, never a new way to bypass a check that
existed before.

Test count: **220 collected cases** (211 functions; +9 from the
pre-existing parametrized permission-matrix tests).
