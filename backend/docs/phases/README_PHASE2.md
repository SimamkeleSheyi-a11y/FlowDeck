# FlowDeck Backend — Phase 2: Authentication & Profiles

Implements: register, email verification (+ resend), login/logout, JWT
access + rotating refresh tokens (refresh as HttpOnly cookie), forgot/reset
password, change password, current-user endpoint, profile edit, avatar
upload/delete. Matches the Phase 1 architecture doc's auth/security design
(Sections 4, 8, 11).

## IMPORTANT — has this been executed?

**No.** This code was written and syntax-checked (`python -m py_compile`,
all 28 files pass) in an environment that has neither Django installed nor
network access to install it (confirmed: `pip install django` and
`apt-get update` both fail — no PyPI/apt reachable). That means:

- Migrations have **not** been generated (`makemigrations` needs Django).
- The test suite below has **not** actually been run.
- `django check` / `manage.py runserver` have **not** actually been run.

I'm not reporting any of those as "passing" because they haven't executed —
only the syntax check has. Run the steps below yourself (or hand this to
Claude Code, which has real package/network access) to get real, verified
results, and paste any failures back for a fix.

## Setup

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Quick local check without Postgres: edit .env and set
#   DATABASE_URL=sqlite:///db.sqlite3
# (Postgres is still the target for later phases — WorkspaceInvitation /
# WorkspaceMembership ownership rely on a Postgres partial unique index.)

python manage.py makemigrations users
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

## Running the test suite

```bash
pytest -v
```

36 tests across 5 files: registration, email verification (+resend),
login/logout/refresh, password reset/change, profile + avatar upload.

## Quick manual smoke test

```bash
# Register
curl -s -X POST http://localhost:8000/api/auth/register/ \
  -H "Content-Type: application/json" \
  -d '{"email":"flash@example.com","password":"S3cure!Passw0rd","password_confirm":"S3cure!Passw0rd","display_name":"Flash"}'

# The verification email prints to the console (EMAIL_BACKEND=console) —
# copy the uid/token out of that link and:
curl -s -X POST http://localhost:8000/api/auth/verify-email/ \
  -H "Content-Type: application/json" \
  -d '{"uid":"<uid>","token":"<token>"}'

# Login (note: -c/-b to persist the refresh cookie across curl calls)
curl -s -c cookies.txt -X POST http://localhost:8000/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"email":"flash@example.com","password":"S3cure!Passw0rd"}'

# Use the returned access token
curl -s http://localhost:8000/api/users/me/ -H "Authorization: Bearer <access>"

# Refresh (reads the cookie, not the body)
curl -s -b cookies.txt -c cookies.txt -X POST http://localhost:8000/api/auth/refresh/
```

## Known limitations / assumptions (please confirm or override)

1. **Registration does not auto-issue tokens.** A user must call `/auth/login/`
   explicitly after registering. Simpler code path than handling "freshly
   registered but unverified" sessions — but a smoother onboarding UX might
   prefer auto-login. Easy to change in Phase 11 (dashboard/onboarding polish)
   if you'd rather.
2. **Login is allowed before email verification.** `is_email_verified` is
   returned on the user object so the frontend can show a banner / gate
   specific actions (e.g. creating a workspace) — it does not block login
   itself. The `IsEmailVerified` permission class is written and ready in
   `permissions.py` for whichever later-phase endpoint should require it.
3. **Password reset / change blacklists every outstanding refresh token**
   for that user (forces logout everywhere). This is a deliberate security
   choice, not explicitly requested — flag if you'd rather scope it to just
   the current session.
4. Migration files are **not** included (see above) — generate them with
   `makemigrations` once Django is installed locally.
5. `django-environ`, Postgres, and Redis are not exercised at all in Phase 2
   (no workspace/board code yet) — `DATABASE_URL` can point at sqlite for a
   fast local Phase 2-only check.

## Files in this phase

```
backend/
  manage.py, requirements.txt, .env.example, pytest.ini, conftest.py, .gitignore
  config/
    settings.py       # env-driven settings, JWT/cookie config, throttle rates
    urls.py            # mounts apps.users.urls under /api/
    exceptions.py       # consistent {"detail","code"} error envelope
    wsgi.py, asgi.py     # asgi.py is plain Django for now; Channels lands Phase 9
  apps/users/
    models.py           # custom User (UUID pk, email login, avatar, bio, is_email_verified)
    managers.py          # UserManager (email-based create_user/create_superuser)
    tokens.py            # EmailVerificationTokenGenerator (separate namespace from password reset)
    cookies.py           # HttpOnly refresh-cookie set/clear helpers
    serializers.py        # register/login/verify/reset/change/profile/avatar serializers
    services.py           # verification + reset emails, blacklist-all-tokens helper
    permissions.py         # IsEmailVerified (not yet wired to any endpoint)
    views.py                # all Phase 2 endpoints
    urls.py                  # /api/auth/... and /api/users/me...
    admin.py                  # Django admin registration
    tests/                     # 36 pytest tests across 5 files
```
