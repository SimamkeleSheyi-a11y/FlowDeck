# FlowDeck Backend — Phase 6: Assignments, Labels, Checklists

Extends `apps.tasks` (no new app) with `TaskAssignee`, `Label`/`TaskLabel`,
and `Checklist`/`ChecklistItem`.

## Execution status — unchanged

Still no Django, no network to install it. 159 tests total (22 new this
phase); all 84 `.py` files pass `python -m py_compile`. New migration
`apps/tasks/migrations/0002_taskassignee_label_tasklabel_checklist_checklistitem.py`
is hand-authored like every prior one — a genuine follow-up migration
(depends on `0001_initial`) rather than folded backward into it, since by
now `0001_initial` may already be applied against a real database. Verify
with `makemigrations --check --dry-run` as always.

## What's new

- **`TaskAssignee`** — multiple assignees per task. Any project member can
  assign, but only *to* someone who themselves has project access —
  "prevent assigning users who are not members of the appropriate
  workspace/project" from the original spec, enforced with the same
  `has_project_access` check used everywhere else.
- **`Label` / `TaskLabel`** — project-scoped tag vocabulary (name + hex
  color), attachable to any task in that project. Label management is open
  to any project member (not OWNER/ADMIN-only) — lightweight collaborative
  tagging, unlike board-structure changes. Unique per `(project, name)`;
  attaching a label from a different project to a task 404s (IDOR-safe,
  same policy as everywhere else).
- **`Checklist` / `ChecklistItem`** — one checklist per task, created
  lazily on first GET or POST (matches the Phase 1 API map's singular
  `/tasks/{id}/checklist/`, not `/checklists/`). Items use the same
  gap-based position scheme as columns/tasks.
- **`TaskSerializer` enriched** — `assignees`, `labels`,
  `checklist_total`, `checklist_done` added to every task response. The
  list endpoint prefetches assignees/labels and annotates the checklist
  counts (`Count` with a filtered `Q`) specifically so these new fields
  don't reintroduce the N+1 pattern already fixed once in Phase 3 —
  verified by `test_task_list_reports_checklist_progress_without_n_plus_one`.
- **`?assignee=me` / `?assignee=<id>` filter** added to the existing task
  list endpoint — a small taste of "My Tasks" ahead of the full dashboard
  in Phase 11.

## REST endpoints added

```
/api/tasks/{id}/assignees/                   POST
/api/tasks/{id}/assignees/{user_id}/          DELETE
/api/tasks/{id}/labels/                        POST  {label_id}
/api/tasks/{id}/labels/{label_id}/              DELETE
/api/tasks/{id}/checklist/                       GET, POST  {text}
/api/checklist-items/{id}/                        PATCH, DELETE
/api/projects/{id}/labels/                         GET, POST  {name, color}
/api/labels/{id}/                                   PATCH, DELETE
```

## Files changed

```
apps/tasks/models.py         +TaskAssignee, Label, TaskLabel, Checklist, ChecklistItem
apps/tasks/services.py         +get_or_create_checklist, next_checklist_item_position
apps/tasks/serializers.py       +8 serializers; TaskSerializer gained 4 fields
apps/tasks/views.py               +7 view classes; list endpoint N+1-hardened
apps/tasks/urls.py                 +8 routes
apps/tasks/admin.py                 registers the 5 new models, 3 new inlines
apps/tasks/migrations/0002_...       new
apps/tasks/tests/               +3 files: test_task_assignees.py (6),
                                   test_labels.py (8), test_checklists.py (8)
```

Not touched: `apps/{users,workspaces,projects,boards}` and their tests.

## Known limitations

- Checklist item reordering isn't implemented — the original spec doesn't
  explicitly call for it (only add/toggle/remove), so it's out of scope
  for now rather than an oversight. Would follow the exact same
  `compute_move_position`-style pattern as columns/tasks if wanted.
- No activity logging on assign/label/checklist changes — `ActivityEvent`
  still doesn't exist until Phase 7, same scope discipline as every prior
  phase.
- Label deletion doesn't check whether it's the last label on any task
  before deleting (unlike column deletion, which blocks on non-empty) —
  removing a label just detaches it everywhere via cascade, which seems
  like reasonable behavior for a tag rather than a structural entity, but
  flag it if you want stricter handling.

Test count: **159 total** (137 + 22 new this phase).
