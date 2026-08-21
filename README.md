# FlowDeck

**FlowDeck is a full-stack project management platform that helps teams organise work through workspaces, projects and interactive Kanban boards.** Teams can assign tasks, use labels and checklists, discuss work through comments, track activity, and move tasks through their workflow with conflict-aware ordering.

**Plan together. Move work forward.**

FlowDeck is a full-stack project and task management application built around workspaces, role-based project access and Kanban boards.

## Stack

**Backend:** Django, Django REST Framework, SimpleJWT, PostgreSQL/SQLite, pytest  
**Frontend:** React, TypeScript, Vite, TanStack Query, dnd-kit

## Product workflow

Register → verify email → create workspace → invite team → create project → add project members → manage tasks on the Kanban board.

Task cards support priorities, dates, assignees, labels, checklists, comments and activity history. Drag-and-drop task movement uses the backend's Phase 8 strict optimistic-concurrency mode so stale moves return a controlled conflict rather than silently overwriting newer task state.

## Repository layout

```text
backend/    Existing Django/DRF API and test suite
frontend/   React + TypeScript product UI
```

## Backend

Use Python 3.12 (the backend intentionally targets Python 3.10–3.12).

```powershell
cd backend
python -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python manage.py migrate
python manage.py check
python -m pytest -q
python manage.py runserver
```

Configure `.env` for either SQLite or PostgreSQL before migrating.

## Frontend

In a second PowerShell window:

```powershell
cd frontend
Copy-Item .env.example .env
npm.cmd install
npm.cmd run build
npm.cmd run dev
```

Then open `http://localhost:5173`.

## Current product scope

- Authentication, verification and profiles
- Workspaces, roles and invitations
- Projects and project membership
- Kanban boards and ordered columns
- Tasks with strict stale-move conflict protection
- Assignees and labels
- Checklists
- Comments and activity history
- Dashboard and responsive frontend

## Product direction

FlowDeck stays focused on project execution and visual work management. Realtime chat/video belongs in a different product; future FlowDeck work should prioritize search, notifications, reporting and production hardening only after the current end-to-end workflow is proven.
