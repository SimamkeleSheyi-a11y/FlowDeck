# Phase 6 corrections, round 2 — real test-run fixes

You ran the real suite (Python 3.12.10, Django 5.0.14, Windows): 187
collected, 174 passed, 13 failed. This round fixes exactly those 13,
diagnosed correctly by category. No migration touched, no test removed, no
assertion weakened.

## Still true: I cannot run these commands here

Nothing has changed about that. No Django, no network to install it in
this sandbox. I have not run `makemigrations --check --dry-run`,
`migrate`, `check`, or `pytest -v` — I can't report real output for them,
only what I fixed and why. You already have a working environment and just
proved it by finding these 13 — sending the real output back is the only
way to actually close this out, and I mean that plainly, not as a
deflection: everything below is my best work against a diagnosis I did not
generate myself.

## 1. JSON null encoding (8 tests)

Confirmed your diagnosis exactly, then searched the *entire* suite (every
`.post`/`.patch`/`.put` call, not just the 8 named ones) for any other
dict body containing a bare `None` without `format="json"` already present
nearby — found no others. `APIClient.post(url, {"key": None})` without
`format="json"` defaults to multipart encoding, which can't represent
`None` and raises `TypeError` before the view is ever reached.

Fixed, all 8, by adding `format="json"`:
- `apps/boards/tests/test_boards_and_columns.py`:
  `test_reorder_column_to_first_position`
- `apps/tasks/tests/test_checklists.py`:
  `test_reorder_item_to_first_position`,
  `test_member_with_project_membership_can_reorder`,
  `test_non_member_cannot_reorder`
- `apps/tasks/tests/test_task_move.py`:
  `test_move_task_to_a_different_column`,
  `test_move_with_stale_version_still_applies_but_flags_conflict`,
  `test_move_with_current_version_reports_no_conflict`,
  `test_cannot_move_task_to_a_column_on_another_project`

Tests that send a *real* UUID string for `after_column_id`/`after_item_id`/
`after_task_id` were never affected — multipart handles strings fine, which
is exactly why only the `None`-sending variants failed.

## 2. Permission-test setup (2 tests)

Confirmed: both tests put a workspace MEMBER with no `ProjectMembership`
row up against a restricted action and expected `403`. The backend was
correct to return `404` instead — a MEMBER with no `ProjectMembership`
can't discover the project at all (Section 6.1), so `403` was never the
right expectation for that setup; it was conflating two different things
(can't see it vs. can see it but isn't allowed to manage it).

Fixed by giving the member explicit `ProjectMembership` *before* the
restricted action, in both cases — now the test isolates the actual thing
under test (role permission), and `403` is the correct, verified response
for "a real project participant who isn't OWNER/ADMIN":
- `apps/boards/tests/test_boards_and_columns.py`:
  `test_member_cannot_create_a_column`
- `apps/projects/tests/test_project_crud.py`:
  `test_member_cannot_update_archive_or_delete_project`

Assertions unchanged (still `403`, not weakened to `404`); only the setup
gained one `ProjectMembership.objects.create(...)` line each.

## 3. Throttling (3 tests)

This one's a genuine bug in my Phase 3 test-fixes round, not a fluke — your
diagnosis is exactly right. `@override_settings(REST_FRAMEWORK=...)` does
make DRF's `api_settings` object refresh (it's wired to Django's
`setting_changed` signal for that purpose) — but
`rest_framework.throttling.SimpleRateThrottle` (which `ScopedRateThrottle`
extends) does:

```python
THROTTLE_RATES = api_settings.DEFAULT_THROTTLE_RATES
```

as a **plain class attribute, evaluated once at import time**. Reassigning
the module-level `api_settings` object later doesn't retroactively update
that already-bound attribute. `@override_settings` was silently a no-op
for the actual rate the throttle enforced — the tests were really running
against the relaxed `1000/min` test-suite-wide rate the whole time, so
`request 4`/`request 3` never hit `429`.

Fixed by patching `ScopedRateThrottle.THROTTLE_RATES` directly —
`unittest.mock.patch.object(ScopedRateThrottle, "THROTTLE_RATES", {...})`
— which targets the exact mapping `get_rate()` reads at request time,
sidestepping the `api_settings` staleness entirely. Explicit
`cache.clear()` before and after each test (on top of the autouse fixture
from the earlier test-isolation round, for a test class where that
guarantee deserves to be unmissable at the call site, not just implicit).

Rewrote `apps/users/tests/test_throttling.py` in full — same three
scenarios and the same required numeric results as before, only the
patching mechanism changed:

| Test | Rate | Requests before block | Blocking request |
|---|---|---|---|
| login | 3/min | 3 (wrong password, only the rate is under test) | 4th → `429` |
| register | 2/min | 2 | 3rd → `429` |
| forgot-password | 2/min | 2 | 3rd → `429` |

Plus the unchanged `test_production_settings_keep_the_real_login_throttle_rate`,
which imports `config.settings` (production) directly and asserts
`"10/minute"` — proving none of this loosened what actually ships.

## Files changed

```
apps/boards/tests/test_boards_and_columns.py    format="json" (1); ProjectMembership setup (1)
apps/tasks/tests/test_checklists.py               format="json" (3)
apps/tasks/tests/test_task_move.py                  format="json" (4)
apps/projects/tests/test_project_crud.py              ProjectMembership setup (1)
apps/users/tests/test_throttling.py                     rewritten — patch.object instead of override_settings
```

Not touched: every migration, every model, every view, every non-test
file. This round is entirely inside the test suite — the bugs were in the
tests, not the application code they were exercising.

## Test count

**Unchanged: 187** (178 `def test_...` functions; the six parametrized
functions in `test_phase6_permission_matrix.py` expand to 15 cases, giving
187 total). No tests added or removed this round — every fix was to
existing test code.
