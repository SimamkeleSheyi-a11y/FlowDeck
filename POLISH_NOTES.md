# FlowDeck launch polish pass

Implemented without changing existing task/board data models or migrations:

- Cleaner global sidebar: Home, Workspaces, Account Settings only.
- Workspace top tabs: Dashboard, Board, Members with active state.
- Dedicated Members area and prominent Invite People action using existing ADMIN/MEMBER roles.
- Clear “All Workspaces” breadcrumb and workspace settings gear.
- Empty-board “Add First Column” flow and Add Task action inside empty columns.
- Stronger dashboard cards, Recent Workspaces metadata, clearer project links and empty states.
- Ctrl/Cmd+K search across accessible workspaces, projects and up to 100 recent/visible tasks.
- Task-move toast with 5-second Undo using the existing strict move API.
- User-facing 409 conflict message; no raw JSON and no false auto-merge claim.
- Keyboard-accessible task cards; Esc closes dialogs/drawers; Ctrl/Cmd+/ opens shortcut help.
- Denser task cards with title, due date, checklist progress and assignee initials.
- Loading skeletons and mobile touch target improvements.
- Production environment hardening with separate production template and secret generator.
- Local development defaults remain local-friendly (SQLite/console email/non-secure localhost cookies).

Not added intentionally:
- Viewer role (backend supports OWNER/ADMIN/MEMBER only).
- WIP limits, templates, calendar, time tracking (v1.1 backlog).
- Destructive global Delete keyboard shortcut.
