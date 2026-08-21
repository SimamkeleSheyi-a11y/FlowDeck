# FlowDeck Backend — Phase 4: Projects & Project Memberships

Implements: project CRUD (create/edit/archive/unarchive/delete), project
membership (add/remove/list), and the Section 6.1 visibility rule from the
Phase 1 architecture doc — OWNER/ADMIN get implicit access to every project
in their workspace, MEMBER needs an explicit `ProjectMembership` row.

## Execution status — same as every prior phase

Still no Django, still no network to install it in this sandbox. 101 tests
now exist (24 new this phase); all 63 `.py` files in the repo pass
`python -m py_compile`. Nothing has actually been run. Migrations
(`apps/projects/migrations/0001_initial.py`) are hand-authored for the same
reason as Phases 2–3 — run `makemigrations --check --dry-run` once Django
is installed to confirm it matches.

## What's new

- **`Project`** — `workspace`, `name`, `description`, `created_by`,
  `created_at`/`updated_at`, `archived_at`.
- **`ProjectMembership`** — binary membership only, no role field (Phase 1
  doc, Section 5.2 / correction #3). `apps/projects/permissions.py` and
  `apps/projects/selectors.py` are the one place the Section 6.1 rule is
  implemented — every view goes through `visible_projects_for_user()` or
  `can_manage_project()` rather than re-deriving the rule.
- **IDOR policy carried over from Phase 3**: a project outside a user's
  visible set is a 404, not a 403 — existence itself is hidden from anyone
  without a workspace relationship (`test_user_from_a_different_workspace_gets_404_not_403`).
- **IsEmailVerified applied throughout** — same as the Phase 3 correction,
  every project endpoint requires `[IsAuthenticated, IsEmailVerified]`; no
  unauthenticated project endpoint exists at all (nothing analogous to the
  invitation preview).
- **N+1 avoided from the start** this time — the project list endpoint uses
  the same `Prefetch(to_attr=...)` pattern the Phase 3 correction
  introduced for workspaces, plus `LimitOffsetPagination`, so this phase
  doesn't need its own later correction round for the same issue.
  (`test_project_list_is_paginated_and_has_no_n_plus_one`)
- **Archive vs. delete** — the original task spec lists both as separate
  actions; implemented as `POST /projects/{id}/archive/` and `/unarchive/`
  (toggle `archived_at`) plus a real `DELETE`. Archived projects are
  excluded from the default list (`?include_archived=true` to see them).
  Delete is a hard delete for now — nothing downstream references `Project`
  yet (boards/tasks land in Phase 5, `ActivityEvent` in Phase 7), so there's
  no cascade-delete-of-history concern yet; worth revisiting once there is.
- **Can't add someone to a project unless they're already in the
  workspace** — mirrors the task-assignment constraint from the original
  spec, enforced here since project membership is the first place that
  rule applies (`test_cannot_add_someone_outside_the_workspace_to_a_project`).

## REST endpoints added

```
/api/projects/                              GET (paginated, filterable by
                                              ?workspace= and
                                              ?include_archived=true), POST
/api/projects/{id}/                          GET, PATCH, DELETE
/api/projects/{id}/archive/                   POST
/api/projects/{id}/unarchive/                  POST
/api/projects/{id}/members/                     GET, POST
/api/projects/{id}/members/{user_id}/            DELETE
```

## Files added

```
apps/projects/
  models.py         Project, ProjectMembership
  permissions.py     get_workspace_role, has_project_access, can_manage_project
  selectors.py        visible_projects_for_user — the Section 6.1 query
  serializers.py        Project(Create/Update), ProjectMembership(Add)
  views.py                all endpoints above
  urls.py, admin.py, apps.py
  migrations/0001_initial.py
  tests/
    test_project_crud.py         (10 tests)
    test_project_visibility.py    (7 tests — the Section 6.1 rule directly)
    test_project_membership.py     (7 tests)
```

Modified: `config/settings.py` (registered `apps.projects`), `config/urls.py`
(mounted its routes). Nothing in `apps/users/` or `apps/workspaces/`
touched.

## Known limitations / assumptions

- `has_project_access()` in `permissions.py` isn't called by any view yet
  (visibility is enforced via the `visible_projects_for_user()` queryset
  instead) — kept because Phase 9's WebSocket authorization will need
  exactly this kind of single-object boolean check, not a queryset.
- Project deletion is OWNER/ADMIN (matches the Phase 1 permission matrix
  row for "Archive/delete project"); if you want deletion restricted to
  OWNER-only the way workspace deletion is, that's a one-line change.
- No activity logging or notifications on project events yet — those
  models don't exist until Phase 7 and Phase 10, same scope discipline as
  every prior phase.

Test count: **101 total** (36 users, 41 workspaces, 24 projects).
