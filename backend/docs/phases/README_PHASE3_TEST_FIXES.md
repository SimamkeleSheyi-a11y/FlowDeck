# Test isolation fixes (post-Phase 3, pre-Phase 4)

Fixes the root cause you found by actually running the suite: 33 passed, 7
failed, 37 errored, with the errors traced to `_login()` helpers hammering
the real `/api/auth/login/` endpoint, tripping the production 10/minute
throttle, and then crashing on `response.data["access"]` with a misleading
`KeyError` once a 429 came back instead of a 200.

## Still true, unchanged: I cannot run this here

Same constraint as every phase so far — no Django installed in this
sandbox, no network to install it. I have **not** run `manage.py check`,
`makemigrations --check --dry-run`, `migrate`, or `pytest` here, and I'm
not reporting numbers for any of them. What follows is what I changed and
why; the exact results have to come from actually running these commands —
which you've already shown you can do. Commands to get them:

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate
pytest -v
```

I'd genuinely like to see the real output of those four — happy to fix
whatever comes back red.

## What changed

### 1. Non-login tests switched to `force_authenticate`, not real login

In `apps/workspaces/tests/*.py` (all 4 files) and
`apps/users/tests/test_profile.py`, the `_login()` helper (renamed
`_authenticate()`) now does:

```python
def _authenticate(api_client, user):
    api_client.force_authenticate(user=user)
```

instead of POSTing to `/api/auth/login/`. These tests were never actually
testing login — they just needed an authenticated request context — so
hitting the real endpoint dozens of times across the full suite was both
slower and, as you found, unstable against the login throttle. Every
existing call site (`_authenticate(api_client, user)`) is unchanged in
behavior; only the helper's internals changed, so no individual test's
logic needed touching.

**Real login is deliberately kept** in the two places that are actually
about login/auth mechanics:
- `apps/users/tests/test_login_logout.py` — untouched, still exercises the
  real endpoint for all of login/logout/refresh.
- `apps/users/tests/test_password_reset_change.py`'s
  `test_change_password_succeeds_and_forces_relogin` — needs a *genuine*
  refresh cookie to verify it gets invalidated after a password change;
  `force_authenticate` doesn't produce one, so this one couldn't move.
  (`test_change_password_requires_correct_old_password`, which didn't need
  that, was switched to `force_authenticate`.)

**Not touched**: `apps/projects/tests/*.py` still use the old real-login
`_login()` pattern. You said not to start Phase 4, and I've read that as
"don't touch Phase 4 files this turn" — but they have the identical bug and
will hit the same throttle/KeyError failure mode in a full run. Flag it and
I'll apply the same fix there.

### 2. `_login()`/login calls now assert status before indexing `.data["access"]`

Applied to every place that still does a real login and reads the response
body immediately after (`test_login_logout.py`'s two spots,
`test_password_reset_change.py`'s remaining real-login test):

```python
assert login_response.status_code == status.HTTP_200_OK, (
    f"Login failed unexpectedly: {login_response.status_code} {login_response.data}"
)
access = login_response.data["access"]
```

A future failure here shows the actual status and body (e.g. a 429 and its
throttle message) instead of a bare `KeyError: 'access'`.

### 3. Cross-test throttle bleed fixed at the root: cache cleared every test

Added an autouse fixture to the root `conftest.py`:

```python
@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()
```

DRF's throttle counters live in Django's cache, not the database —
pytest-django's per-test transaction rollback (which resets DB state)
doesn't touch the cache at all. Without this, a request count from one
test could carry into an unrelated later test and make failures depend on
run order. This was very likely contributing to the scale of the failure
(37 errors, not just a handful) beyond what any single test's own login
calls would explain.

### 4. Dedicated test settings — throttle rates raised, never disabled

New `config/settings_test.py`, imports everything from the real
`config.settings` and overrides exactly two things:

- `DEFAULT_THROTTLE_RATES` raised to `1000/min` across the board — headroom
  for the handful of tests that legitimately still call real login/register/
  password-reset endpoints multiple times in one run. **Production
  (`config/settings.py`) is completely untouched** — still `10/minute` for
  login, `5/hour` for the rest. `manage.py` (check/makemigrations/migrate/
  runserver) still defaults to `config.settings`; only `pytest.ini`'s
  `DJANGO_SETTINGS_MODULE` points at `config.settings_test`.
- `SECRET_KEY` set to a real random 48-byte value (`secrets.token_urlsafe(48)`),
  replacing the `"insecure-dev-key-change-me"` placeholder for test runs
  specifically — should clear whatever `SECRET_KEY`-related warning you saw
  from `manage.py check`. This key is test-only; production still sets its
  own via the `SECRET_KEY` environment variable exactly as before.

### 5. Dedicated throttle tests — proving it still works, not disabling it

New `apps/users/tests/test_throttling.py`, 4 tests:

- `test_login_is_throttled_after_the_configured_rate`,
  `test_register_is_throttled_after_the_configured_rate`,
  `test_forgot_password_is_throttled_after_the_configured_rate` — each uses
  `@override_settings(REST_FRAMEWORK=...)` to deliberately re-tighten one
  throttle scope to a small number just for that test (e.g. `3/min` for
  login), makes exactly that many requests and confirms none are blocked,
  then confirms the next one is `429`. Django/DRF support this cleanly —
  DRF listens for `REST_FRAMEWORK` changes via the `setting_changed`
  signal specifically so `override_settings` works in tests.
- `test_production_settings_keep_the_real_login_throttle_rate` — imports
  `config.settings` (not the test settings module) directly and asserts
  its login rate is still `"10/minute"`, as a direct check that fixing test
  isolation didn't quietly loosen what actually ships.

## Files changed this pass

```
conftest.py                                    autouse cache-clearing fixture
config/settings_test.py                          new — test-only settings
pytest.ini                                        DJANGO_SETTINGS_MODULE → settings_test
apps/users/tests/test_login_logout.py               2 defensive status asserts
apps/users/tests/test_password_reset_change.py       1 test → force_authenticate,
                                                        1 test gets defensive assert
apps/users/tests/test_profile.py                       authed_client → force_authenticate
apps/users/tests/test_throttling.py                     new — 4 tests
apps/workspaces/tests/test_workspace_crud.py              _login → _authenticate (force_authenticate)
apps/workspaces/tests/test_membership_roles.py              same
apps/workspaces/tests/test_ownership_transfer.py              same
apps/workspaces/tests/test_invitations.py                       same
```

Not touched: every application file (`models.py`, `views.py`, `services.py`,
etc.) from Phases 2–4, and `apps/projects/tests/*.py` (flagged above).

Test count: **105 total** (101 + 4 new throttle tests). All 66 `.py` files
in the repo pass `python -m py_compile`.
