# FlowDeck

**Plan together. Move work forward.**

FlowDeck is a collaborative project-management platform — workspaces,
projects, Kanban boards, tasks with assignees/labels/checklists, comments,
and a server-authoritative activity history. Built as a portfolio-quality
Django/DRF backend across eight incremental phases, each with its own
regression tests.

This README covers setup, the current API surface, and the permission
model. Phase-by-phase development notes (including corrections made after
real test runs) live in [`docs/phases/`](docs/phases/) — kept for a
transparent record of how the backend evolved, not required reading to run
the project.

---

## Features by phase

| Phase | What it added |
|---|---|
| 2 | Authentication: register, email verification (+resend), login/logout, JWT access + rotating refresh (HttpOnly cookie), forgot/reset password, change password, profile + avatar |
| 3 | Workspaces, roles (OWNER/ADMIN/MEMBER), invitations (hashed tokens, expiry, send/accept/revoke), atomic ownership transfer |
| 4 | Projects, project membership, the visibility rule OWNER/ADMIN implicitly reach every project in their workspace, MEMBER needs explicit membership |
| 5 | Boards (auto-created per project) + columns (CRUD, reorder), tasks (CRUD, move with optimistic concurrency) |
| 6 | Task assignees, project-scoped labels, per-task checklists |
| 7 | Comments (soft-delete, author-only edit/delete), server-authoritative activity history |
| 8 | Full board state endpoint, self-healing position rebalancing, optional strict conflict mode on task move |

Boards/tasks/comments are backend-only so far — no frontend has been built
in any phase of this project. Real-time collaboration (WebSockets),
notifications, dashboard/search, attachments, and deployment hardening are
future phases — see [Known limitations](#known-limitations) and
[Future improvements](#future-improvements).

---

## Technology stack

- **Backend**: Python, Django 5.0.x, Django REST Framework
- **Auth**: `djangorestframework-simplejwt` — JWT access token + rotating refresh token stored as an HttpOnly cookie
- **Database**: PostgreSQL (production target); SQLite works for local/dev runs — nothing in the schema is Postgres-only except the partial unique indexes used for workspace ownership and pending-invitation uniqueness, both of which SQLite also supports
- **Other**: `django-cors-headers`, `django-environ`, Pillow (avatar images)
- **Testing**: `pytest`, `pytest-django`

### Python version

**3.10–3.12. Recommended: 3.12** (tested on 3.12.10). Django 5.0.x does not
support Python 3.13+; this is enforced (not just documented) — `manage.py`
and `conftest.py` both check `sys.version_info` before importing Django at
all. A `.python-version` file is included for pyenv/asdf.

---

## Installation

```bash
git clone <your-repo-url>
cd flowdeck/backend

python3 --version   # confirm 3.10-3.12
python3 -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Environment setup

```bash
cp .env.example .env
```

Edit `.env` as needed. Key variables:

| Variable | Purpose | Local default |
|---|---|---|
| `DEBUG` | Django debug mode | `True` |
| `SECRET_KEY` | Django signing key | placeholder — **set a real one for anything beyond local use** |
| `DATABASE_URL` | `postgres://...` or `sqlite:///db.sqlite3` | Postgres in `.env.example`; switch to sqlite for a quick local check |
| `FRONTEND_URL` | Used to build email links (verification, password reset, invitations) | `http://localhost:5173` |
| `CORS_ALLOWED_ORIGINS` | Allowed frontend origins | `http://localhost:5173` |
| `EMAIL_BACKEND` | `django.core.mail.backends.console.EmailBackend` for local dev (prints emails instead of sending) | console |

## Migrations

```bash
python manage.py makemigrations --check --dry-run   # should report "No changes detected."
python manage.py migrate
```

All migrations in this repo are hand-authored (development happened
without a local Django install at various points) rather than
machine-generated — functionally correct, but if the check above ever
reports a difference, trust Django's autodetector over the existing file
and let it generate the difference.

## Create a superuser

```bash
python manage.py createsuperuser
```

## Run the server

```bash
python manage.py runserver
```

Django admin at `/admin/`; API under `/api/` (see below).

## Run tests

```bash
pytest -v
```

Uses `config/settings_test.py` (relaxed throttle rates for test-suite
headroom, a random test-only `SECRET_KEY`) — production settings
(`config/settings.py`) are unaffected; `manage.py` always uses those.

---

## Main API endpoints

```
Auth
  POST   /api/auth/register/
  POST   /api/auth/verify-email/
  POST   /api/auth/resend-verification/
  POST   /api/auth/login/
  POST   /api/auth/refresh/
  POST   /api/auth/logout/
  POST   /api/auth/password/forgot/
  POST   /api/auth/password/reset/
  POST   /api/auth/password/change/
  GET    /api/users/me/                          PATCH
  POST   /api/users/me/avatar/                    DELETE

Workspaces
  GET    /api/workspaces/                        POST
  GET    /api/workspaces/{id}/                     PATCH   DELETE
  POST   /api/workspaces/{id}/leave/
  POST   /api/workspaces/{id}/ownership/transfer/
  GET    /api/workspaces/{id}/members/
  PATCH  /api/workspaces/{id}/members/{user_id}/    DELETE
  GET    /api/workspaces/{id}/invitations/           POST
  DELETE /api/workspaces/{id}/invitations/{id}/
  GET    /api/invitations/{token}/                    (public preview)
  POST   /api/invitations/{token}/accept/

Projects
  GET    /api/projects/                          POST
  GET    /api/projects/{id}/                       PATCH   DELETE
  POST   /api/projects/{id}/archive/                POST (unarchive/)
  GET    /api/projects/{id}/members/                 POST
  DELETE /api/projects/{id}/members/{user_id}/

Boards & columns
  GET    /api/boards/{id}/
  GET    /api/boards/{id}/full/                    (Phase 8 — see below)
  GET    /api/boards/{id}/columns/                  POST
  PATCH  /api/columns/{id}/                          DELETE
  POST   /api/columns/{id}/reorder/

Tasks
  GET    /api/tasks/                              POST
  GET    /api/tasks/{id}/                           PATCH   DELETE
  POST   /api/tasks/{id}/move/                       (Phase 8 strict mode — see below)
  POST   /api/tasks/{id}/assignees/                    DELETE (…/{user_id}/)
  POST   /api/tasks/{id}/labels/                        DELETE (…/{label_id}/)
  GET    /api/tasks/{id}/checklist/                      POST
  PATCH  /api/checklist-items/{id}/                        DELETE
  POST   /api/checklist-items/{id}/reorder/
  GET    /api/projects/{id}/labels/                         POST
  PATCH  /api/labels/{id}/                                    DELETE

Comments & activity
  GET    /api/tasks/{id}/comments/                POST
  PATCH  /api/comments/{id}/                        DELETE   (author only)
  GET    /api/tasks/{id}/activity/                    (read-only)
```

---

## Permission model

Three workspace roles: **OWNER**, **ADMIN**, **MEMBER**.

- **OWNER** — full workspace control, the only role that can manage other
  admins, remove an admin, revoke an admin-role invitation, or delete the
  workspace. Exactly one OWNER per workspace, enforced by a database
  constraint (not just application logic).
- **ADMIN** — manages projects and non-admin members, sends/manages
  invitations (except admin-role ones).
- **MEMBER** — collaborates on projects they're explicitly added to.

**Project visibility rule** (applies everywhere a project, board, task,
comment, label, or checklist is reached): OWNER and ADMIN implicitly reach
every project in their workspace, whether or not they hold an explicit
`ProjectMembership` row. MEMBER needs that explicit row. A project (or
anything under it) outside what a user can reach returns **404, not
403** — existence itself is hidden from anyone without a relationship to
the workspace, not just its contents.

**Task-level work** (create/edit/move/delete tasks, comment, assign,
label, checklist) is open to any project member equally — not
OWNER/ADMIN-gated, matching the collaborative day-to-day model. **Board
structure** (create/rename/delete/reorder columns) is OWNER/ADMIN-only.
**Comment edit/delete** is restricted further still, to the comment's own
author — not even OWNER/ADMIN can touch someone else's comment.

Every write-capable endpoint additionally requires a verified email
(`IsEmailVerified`).

---

## Phase 8 in detail

### `GET /api/boards/{board_id}/full/`

Everything a drag-and-drop board view needs in one round-trip: columns in
position order, each with its tasks in position order, each task carrying
assignees, labels, checklist progress, priority, dates, and version. N+1-safe
regardless of task count. The plain `GET /api/boards/{id}/` endpoint from
Phase 5 is unchanged — this is a new, separate endpoint.

<details>
<summary>Example response</summary>

```json
{
  "id": "b1a2c3d4-0000-4000-8000-000000000001",
  "project_id": "a1a2c3d4-0000-4000-8000-000000000001",
  "created_at": "2026-08-01T09:00:00Z",
  "columns": [
    {
      "id": "c1a2c3d4-0000-4000-8000-000000000001",
      "name": "To Do",
      "position": 2000.0,
      "created_at": "2026-08-01T09:00:00Z",
      "tasks": [
        {
          "id": "t1a2c3d4-0000-4000-8000-000000000001",
          "column_id": "c1a2c3d4-0000-4000-8000-000000000001",
          "project_id": "a1a2c3d4-0000-4000-8000-000000000001",
          "title": "Build authentication API",
          "description": "Implement JWT authentication...",
          "priority": "HIGH",
          "position": 1000.0,
          "start_date": null,
          "due_date": "2026-08-30",
          "is_completed": false,
          "version": 2,
          "assignees": [
            { "id": "...", "user": { "id": "...", "display_name": "Flash", "...": "..." }, "assigned_at": "..." }
          ],
          "labels": [{ "id": "...", "name": "Backend", "color": "#6B7280", "created_at": "..." }],
          "checklist_total": 4,
          "checklist_done": 2,
          "created_by": { "id": "...", "display_name": "Flash", "...": "..." },
          "created_at": "...",
          "updated_at": "..."
        }
      ]
    }
  ]
}
```
</details>

### Position rebalancing

Not an endpoint — a transparent, self-healing behavior inside the existing
column-reorder, task-move, and checklist-item-reorder endpoints. Positions
are gap-based floats (`1000.0`, `2000.0`, ...); repeatedly inserting in the
same spot halves the remaining gap each time, which would eventually run
into float-precision limits. Every insert-between-two-neighbors path now
checks the gap first — if it's fallen below a safety threshold, every
sibling is reassigned clean, evenly-spaced positions before the insert is
computed, invisibly to the caller. Nothing about the request/response shape
of any reorder/move endpoint changes because of this.

### Strict task-move conflict mode

`POST /api/tasks/{id}/move/` gained an optional `strict` field.

**Default (`strict` omitted or `false`) — unchanged since Phase 5:**

```json
// request
{ "column_id": "c...", "after_task_id": null, "version": 3 }

// response — 200 OK, even if version was stale: the move still applies
{
  "id": "t...", "column_id": "c...", "version": 4,
  "conflict": true,
  "...": "... (full task state)"
}
```

**With `"strict": true`, a stale version is rejected instead of applied:**

```json
// request
{ "column_id": "c...", "after_task_id": null, "version": 3, "strict": true }

// response — 409 CONFLICT if version 3 is no longer current
{
  "detail": "This task was changed since you last loaded it — refresh and try again.",
  "code": "version_conflict",
  "current": { "id": "t...", "version": 5, "...": "... (full, untouched task state)" }
}
```

The task's column, position, and version are completely untouched when a
`409` is returned — no move applied, no activity event logged.

---

## Current test result

**211 test functions, 220 collected pytest cases** (the gap: six
parametrized permission-matrix test functions expand to 15 individual
cases). This count is computed from the source — the development
environment used to build this backend has no local Django install, so
these numbers were never confirmed by an actual `pytest` run at every
phase; the last **independently confirmed run** (Python 3.12.10, Django
5.0.14) was at the Phase 6 checkpoint: **187 passed, 0 failed**. Phases 7
and 8 add 33 more tests on top of that baseline, believed correct by the
same reasoning and care that made the Phase 6 fixes land correctly, but
not yet independently re-run. Please run `pytest -v` after installing and
treat that output as authoritative over any count stated here.

---

## Known limitations

- No frontend in any phase — this is a backend-only build throughout.
- No real-time collaboration yet (WebSockets/Redis) — planned, not started.
- No notification system yet.
- No dashboard/global search/saved filters yet (basic per-list filtering
  exists — e.g. `?priority=`, `?assignee=me` on the task list).
- No file attachments on tasks yet.
- Activity logging doesn't cover board/column structural changes (create/
  rename/delete/reorder) — only workspace, project, task, and comment
  events are logged.
- Migrations throughout are hand-authored rather than machine-generated;
  functionally verified but worth a `makemigrations --check --dry-run`
  pass before relying on them in a new environment.
- Rate limiting, security hardening pass, and load/perf testing haven't
  had a dedicated phase yet.

## Future improvements

Roughly in priority order for a next iteration:

1. Real-time collaboration (Django Channels + Redis) — live board/task/
   comment updates across connected clients, ticket-based WebSocket auth.
2. In-app notifications (assigned-to-you, mentioned, due-soon, invited).
3. Dashboard: My Tasks, Due Soon, Overdue, Recent Activity, global search.
4. File attachments on tasks (object storage, not DB-stored binaries).
5. Activity logging extended to board/column structural changes.
6. Security hardening pass + broader test coverage (the original project
   brief's Phase 13) and a deployment/CI setup (Phase 14) — Docker,
   Postgres + Redis in CI, HTTPS/WSS termination notes.
7. A frontend, at some point — nothing here has one yet.
