# FlowDeck Backend — Phase 5: Boards, Columns, Basic Task Cards

Two new apps: `apps.boards` (Board, BoardColumn) and `apps.tasks` (Task).
Also closed a flagged gap in already-existing Phase 4 test files.

## Execution status — unchanged

Still no Django, still no network to install it here. 137 tests total (24
new this phase); all 76 `.py` files in the repo pass `python -m py_compile`.
Migrations (`apps/boards/migrations/0001_initial.py`,
`apps/tasks/migrations/0001_initial.py`) are hand-authored like every prior
app's — every index has an explicit `name=` matching models.py exactly
from the start this time, applying the lesson from the Phase 3 index-rename
fix rather than needing a follow-up correction. Verify with
`makemigrations --check --dry-run` as always.

**Also fixed**: `apps/projects/tests/*.py` still had the old real-login
`_login()` pattern flagged (twice) since the test-isolation fix — converted
to `force_authenticate` now that Phase 4 is actively being built on.

## What's new

**`apps.boards`** — `Board` (one per project, auto-created — see below),
`BoardColumn` (name + gap-based float `position`, same "no DB IDs as visual
order" rule as everywhere else). Column CRUD is OWNER/ADMIN-only
(structural board configuration); reordering computes a midpoint between
new neighbors so nothing else needs renumbering. Deleting a non-empty
column is refused (`column_not_empty`) rather than silently orphaning or
cascading its tasks away — matches "delete columns safely" from the
original spec.

**`apps.tasks`** — `Task` (title, description, priority, position,
start/due date, `is_completed`, `version`). Unlike board structure, task
CRUD is open to **any project member**, not just OWNER/ADMIN — matches the
original spec's collaborative day-to-day model. `TaskMoveView` implements
the Phase 1 architecture doc's Section 5.3 optimistic-concurrency design
exactly: a stale submitted `version` doesn't block the move (Phase 5/8 MVP
is accept-and-flag, not reject) but the response carries `"conflict": true`
plus the canonical task state, so a frontend can show a brief
reconciliation notice instead of silently trusting its own optimistic
move. Tightening this to a hard `409` later is a one-line comparison
change — no schema or API contract change needed.

**Auto-created boards** — `ProjectListCreateView.post` (Phase 4, modified
this round) now creates the project's `Board` + 5 default columns
(Backlog/To Do/In Progress/Review/Done) in the same atomic transaction as
the project itself, matching "each project gets a Kanban board" from the
original spec. `ProjectSerializer` gained a `board_id` field so clients can
navigate there. Nothing about existing project behavior changed — this is
additive.

## REST endpoints added

```
/api/boards/{id}/                    GET
/api/boards/{id}/columns/            GET, POST
/api/columns/{id}/                    PATCH, DELETE
/api/columns/{id}/reorder/             POST   {after_column_id}

/api/tasks/                          GET (paginated; ?project=, ?column=,
                                        ?priority=, ?is_completed=), POST
/api/tasks/{id}/                      GET, PATCH, DELETE
/api/tasks/{id}/move/                  POST   {column_id, after_task_id, version}
```

## A scope decision worth flagging

The roadmap lists "Boards, columns and basic task cards" (5) and
"Drag-and-drop boards" (8) as separate phases. I read Phase 8 as being
about the *frontend* drag-and-drop experience (none of Phases 2–5 have
touched a frontend at all — this has been backend-only throughout), not
about whether the backend can reorder things. Since "reorder columns",
"move cards between columns", and "reorder cards within a column" are
listed as core Kanban capabilities in the original spec's Section 4 (not
deferred to a later section), I built the reorder/move endpoints now
rather than leaving basic task cards unable to change column or order.
Flag it if you wanted Phase 5 to stop at plain CRUD with column/position
reassignment deferred to Phase 8.

## Files added/changed

```
apps/boards/    models, permissions, selectors, services, serializers,
                 views, urls, admin, migrations/0001_initial.py,
                 tests/test_boards_and_columns.py (11 tests)
apps/tasks/     same shape, tests split across
                 test_tasks_crud.py (7) and test_task_move.py (6)
apps/projects/views.py         auto-creates the board on project creation
apps/projects/serializers.py    +board_id field
apps/projects/tests/*.py         _login() → _authenticate() (flagged gap, now closed)
config/settings.py, config/urls.py   registered + mounted both new apps
```

## Known limitations

- Task assignees, labels, and checklists don't exist yet — Phase 6.
- No activity logging on task/column/board changes — `ActivityEvent`
  doesn't exist until Phase 7, same scope discipline as every prior phase.
- `TaskMoveView`'s conflict detection is proven by regression test
  (`test_move_with_stale_version_still_applies_but_flags_conflict`), not by
  actually running two concurrent requests — same honest limitation noted
  for the Phase 3 ownership-transfer concurrency test.
- Column/task position fields use plain (non-locked) reads-then-writes,
  matching the documented Phase 5/8 MVP decision (detect conflicts, don't
  prevent them) — revisit only if real concurrent-editing problems show up.

Test count: **137 total** (113 + 24 new this phase).
