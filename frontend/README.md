# FlowDeck Frontend

React + TypeScript frontend for the existing FlowDeck Django/DRF backend.

## Included in this frontend pass

- Login / registration
- Email verification link handling
- Forgot/reset password flows
- Persistent session restoration using the backend's HttpOnly refresh cookie
- Dashboard with project, workspace, assigned-task and overdue summaries
- Workspace creation and workspace team view
- Workspace invitations
- Project creation
- Project member management
- Full Kanban board loaded from `GET /api/boards/{id}/full/`
- Task creation
- Drag-and-drop task movement using Phase 8 strict version conflict mode
- Task editing (title, description, priority, due date)
- Assignees
- Project labels + task labels
- Checklist items
- Comments
- Activity history
- Responsive desktop/mobile layout
- Profile settings

## Run locally

Backend should be running at `http://127.0.0.1:8000` and allow `http://localhost:5173` in CORS.

```powershell
cd frontend
Copy-Item .env.example .env
npm.cmd install
npm.cmd run build
npm.cmd run dev
```

Open `http://localhost:5173`.

The default `.env.example` points at:

```text
VITE_API_URL=http://127.0.0.1:8000/api
```

## Local email verification

The backend currently defaults to Django's console email backend. Register or resend verification, then copy the verification URL printed in the backend terminal and open it in the browser.

## Next hardening pass

After the local product walkthrough is green:

1. Frontend tests for auth and board interactions.
2. Production deployment configuration.
3. Optional notification center and global search.
4. Optional realtime board updates only after the core workflow is stable.
