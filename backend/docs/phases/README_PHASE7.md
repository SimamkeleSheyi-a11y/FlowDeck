# FlowDeck Backend — Phase 7: Comments & Activity History

Two new apps — `apps.comments` and `apps.activity` — plus activity-logging
calls added into the existing `apps.tasks`, `apps.projects`, and
`apps.workspaces` views. Built on top of the accepted Phase 6 baseline
(`flowdeck-phase6-corrections-2-backend.zip`), no existing migration
touched or squashed.

## Execution status — unchanged

Still no Django, no network to install it here. Test count is **computed
from source, not from a run** — same honest distinction as last round:

- **195 test *functions*** (178 preserved + 17 new: 8 comments, 9 activity)
- **204 test *cases*** — the 6 pre-existing parametrized functions in
  `test_phase6_permission_matrix.py` still expand to 15 cases, same +9 gap
  as before. `pytest -v` will report 204 collected, not 195 or 195+17=212.

Migrations: `apps/comments/migrations/0001_initial.py` and
`apps/activity/migrations/0001_initial.py` are new; all 6 pre-existing
migration files (users, workspaces, projects, boards, tasks ×2) are
byte-for-byte untouched — confirmed by listing the migrations directory
before and after this phase. Every index in both new migrations has an
explicit `name=` matching `models.py` exactly, from the start.

## What's new

**`apps.comments`** — `Comment` (soft-delete via `deleted_at`, so an
activity event referencing a deleted comment still points at a real row —
Phase 1 doc, Section 5). Any project member can comment; only the
comment's own author can edit or delete it — not even OWNER/ADMIN can
touch someone else's comment, per the original spec's literal wording
("edit *their own* comments").

**`apps.activity`** — `ActivityEvent` with the full `ActivityEventType`
enum from the Phase 1 architecture doc's Section 5.4, plus one addition
(`WORKSPACE_CREATED`, an obvious gap in the original list — safe to add
since `choices` on a `CharField` is a Python-level constraint, not a DB
one, so extending it later never needs a migration either). `workspace`/
`project`/`task` all use `on_delete=SET_NULL`, never `CASCADE` — deleting
any of those must not delete the history of what happened to it (Section
16: "do not blindly cascade-delete important historical records").
`log_activity()` in `apps/activity/services.py` is the single write path
every other app calls — nothing creates `ActivityEvent` rows directly, and
nothing accepts activity data as client input (Section 8: "never trust the
frontend to generate authoritative history").

**Activity logging wired into existing views** — 25 call sites added
across three already-existing, already-tested apps, every one a pure
additive side-effect after a mutation already succeeded (never touching
response shape, status code, or existing logic):

| App | Events logged |
|---|---|
| `apps.workspaces` | `WORKSPACE_CREATED`, `WORKSPACE_MEMBER_JOINED` (invitation accepted), `WORKSPACE_MEMBER_ROLE_CHANGED`, `WORKSPACE_MEMBER_REMOVED` (both admin-removed and self-left, flagged via metadata), `WORKSPACE_OWNERSHIP_TRANSFERRED` |
| `apps.projects` | `PROJECT_CREATED`, `PROJECT_MEMBER_ADDED`, `PROJECT_MEMBER_REMOVED` |
| `apps.tasks` | `TASK_CREATED`, `TASK_MOVED` (with from/to column names), `TASK_PRIORITY_CHANGED`/`TASK_DUE_DATE_CHANGED`/`TASK_COMPLETED`/`TASK_REOPENED` (detected by comparing old vs. new values in `TaskDetailView.patch`, falling back to generic `TASK_UPDATED` if none of those specifically changed), `TASK_DELETED`, `TASK_ASSIGNED`/`TASK_UNASSIGNED`, `LABEL_ADDED`/`LABEL_REMOVED`, `CHECKLIST_ITEM_ADDED`, `CHECKLIST_ITEM_COMPLETED` (only when `is_done` flips to `True`, not on every edit) |
| `apps.comments` | `COMMENT_ADDED`, `COMMENT_EDITED`, `COMMENT_DELETED` |

Matches the original spec's example activity lines directly: "Flash
created this task" → `TASK_CREATED`; "Simamkele moved Dashboard Design from
To Do to In Progress" → `TASK_MOVED` with exactly that from/to metadata;
"Priority changed from Medium to High" → `TASK_PRIORITY_CHANGED` with
`{"from": "MEDIUM", "to": "HIGH"}`; "Task completed" → `TASK_COMPLETED`;
"Flash added a comment" → `COMMENT_ADDED`.

## Safety check on the 187 preserved tests

Every one of the 25 new `log_activity()` calls was placed in a
**POST/PATCH/DELETE** (mutation) method — never in a `GET`/list method.
This matters specifically because three existing tests bound query counts
with `django_assert_max_num_queries`
(`test_workspace_list_does_not_grow_queries_with_workspace_count`,
`test_project_list_is_paginated_and_has_no_n_plus_one`,
`test_task_list_reports_checklist_progress_without_n_plus_one`) — all
three wrap only a `GET` call; their setup `POST`s (now one query heavier
each, for the activity insert) happen *outside* the measured block in
every case, so none of those bounds are affected. No response body or
status code was changed by any of the 25 additions — checked individually
during each edit, not just asserted after the fact.

## REST endpoints added

```
/api/tasks/{id}/comments/        GET (paginated), POST {body}
/api/comments/{id}/                PATCH {body}, DELETE   (author only)
/api/tasks/{id}/activity/           GET (paginated, newest first)
```

## Files changed

```
apps/comments/    new app — models, permissions, serializers, views,
                    urls, admin, migrations/0001_initial.py,
                    tests/test_comments.py (8 tests)
apps/activity/     new app — same shape,
                     tests/test_activity_feed.py (9 tests)
apps/tasks/views.py       +13 log_activity call sites (imports added)
apps/projects/views.py      +3 log_activity call sites
apps/workspaces/views.py      +6 log_activity call sites
config/settings.py, config/urls.py   registered + mounted both new apps
```

Not touched: every migration file from Phases 2–6, every model in the five
pre-existing apps, and all 178 pre-existing test functions.

## Known limitations

- No activity logging on board/column changes (create/rename/delete/
  reorder) — the `ActivityEventType` enum as documented in Phase 1 doesn't
  include column-level events, and adding new ones felt like it deserved
  your sign-off rather than a unilateral scope addition on top of an
  already-large phase. Easy to add if wanted.
- `TASK_UPDATED` (the generic fallback) fires on any `PATCH` that doesn't
  touch priority/due_date/is_completed — e.g. a title-only edit. This
  means a title change is logged as an unqualified "task updated" rather
  than a specific "title changed from X to Y"; flag it if you want that
  level of granularity too.
- Comment moderation (OWNER/ADMIN deleting someone else's comment) isn't
  implemented — the original spec only grants authors that power over
  their own comments, so this is a literal reading, not an oversight.

Test count: **204 collected cases** (195 functions; +9 from the
pre-existing parametrized permission-matrix tests).
