# FlowDeck production checklist

This pass intentionally keeps local development behavior unchanged. Production security is controlled with environment variables.

## Before deployment

1. Run `python scripts/generate_secrets.py` and put the two generated values only in your hosting provider.
2. Use PostgreSQL for `DATABASE_URL`.
3. Set `DEBUG=False`.
4. Set the deployed backend host in `ALLOWED_HOSTS`.
5. Set the exact HTTPS frontend origin in `FRONTEND_URL`, `CORS_ALLOWED_ORIGINS`, and `CSRF_TRUSTED_ORIGINS`.
6. Keep `COOKIE_SECURE=True` and `SECURE_SSL_REDIRECT=True`.
7. Use a real SMTP provider for verification/password-reset emails.
8. Set frontend `VITE_API_URL=https://YOUR-BACKEND/api` at build time.
9. Run `python manage.py check --deploy` against production-like environment variables.
10. Run the full backend test suite and `npm run build` before release.

## Launch gates

- Backend: all tests green (local verified target: 220).
- Frontend: TypeScript + Vite production build green.
- Smoke test: register → verify → login → workspace → project → board → task → drag → label/assignee → checklist/comment.
- Confirm cookies and API calls work over HTTPS.
- Confirm verification email arrives outside the console backend.
