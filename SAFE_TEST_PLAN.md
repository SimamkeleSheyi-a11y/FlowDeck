# FlowDeck safe regression plan

Do not delete your current working copy. Extract this package into a new folder and test it independently.

## Gate 1 — backend

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python manage.py check
python -m pytest -q
```

Expected baseline: **220 passed** on the working Python 3.12 environment.

## Gate 2 — frontend

```powershell
cd ..\frontend
npm.cmd install
npm.cmd run build
npm.cmd run dev
```

## Gate 3 — smoke test

1. Register and verify email.
2. Log in.
3. Create/open a workspace.
4. Confirm workspace tabs: Dashboard / Board / Members.
5. Open Members and invite a MEMBER; OWNER can also invite ADMIN.
6. Open Board tab, choose a project board.
7. Create a task and open its details.
8. Add/remove assignee and label.
9. Add/tick checklist item and add a comment; close/reopen to verify persistence.
10. Drag task to another column; confirm toast and test Undo within 5 seconds.
11. Press Ctrl+K and search for a workspace/project/task.
12. Press Ctrl+/ for shortcut help.
13. Resize to mobile width and verify navigation/buttons remain usable.

## Empty board test

The backend normally creates default columns with a new project. To test the launch-critical empty-board UX, use a board that genuinely has zero columns. The UI should show **Add First Column** for OWNER/ADMIN.

## Production gate

Do not reuse local secrets. Follow `PRODUCTION_CHECKLIST.md` and `backend/production.env.example`.
