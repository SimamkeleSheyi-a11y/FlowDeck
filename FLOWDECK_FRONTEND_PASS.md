# FlowDeck Full-Stack Frontend Pass

This package starts from `flowdeck-github-ready.zip` and keeps the existing backend intact while adding a new React + TypeScript frontend.

## Added now

- Responsive FlowDeck product shell
- Authentication pages
- Email verification route
- Password reset routes
- Session refresh support with HttpOnly cookie backend design
- Dashboard
- Workspace list/create
- Workspace detail, members and invitations
- Project create/open
- Project team management
- Full Phase 8 Kanban board integration
- Drag-and-drop task moves using `strict: true`
- Create/edit tasks
- Task priorities and due dates
- Assignees
- Project/task labels
- Checklists
- Comments
- Activity history
- Profile settings

## Validation performed in this environment

- Python `compileall` over backend: PASS
- TypeScript parser/transpile syntax validation over 17 TS/TSX files: PASS (0 syntax errors)

## Validation still required on the user's Windows machine

The sandbox cannot reach npmjs.org, so package installation/build could not be executed here.

Run:

```powershell
cd frontend
npm.cmd install
npm.cmd run build
```

Then run the backend test suite under Python 3.12:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python manage.py check
python -m pytest -q
```
