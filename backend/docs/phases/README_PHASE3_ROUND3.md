# Phase 3 — third correction round

Addresses: Python version pinning, the migration index-rename fix, and two
new admin-permission restrictions (with tests), on top of the test
isolation fixes from the previous round.

## Still true, unchanged: I cannot run this here

Same constraint as every round so far — no Django, no network to install
it, in this sandbox. **I have not run `manage.py check`,
`makemigrations --check --dry-run`, `migrate`, or `pytest` here.** Exact
commands, unchanged from before:

```bash
cd backend
python3 --version   # confirm 3.10-3.12 — see README.md
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate
pytest -v
```

You're the one with a working Django environment now — genuinely, send the
real output whenever you get to it and I'll fix whatever's still red.

## 1. Python version pinned and enforced

New `README.md` states Python 3.10–3.12 (Django 5.0.x doesn't support
3.13+), with 3.12 recommended — matching what you confirmed works
(3.12.10). New `.python-version` (`3.12`) for pyenv/asdf. Enforced, not
just documented: both `manage.py` and `conftest.py` now check
`sys.version_info` before importing Django at all, and exit with one clear
message on an unsupported interpreter instead of letting it fail somewhere
inside Django's own import chain. `requirements.txt` got a matching
comment at the top.

## 2. Migration index-rename fix

Root cause: `apps/{users,workspaces,projects}/models.py` declared their
`Meta.indexes` **without** an explicit `name=`, while the hand-authored
migrations gave those same indexes an explicit name. Since models.py left
it unnamed, a fresh `makemigrations` computed Django's own auto-generated
(hash-based) name for each index, saw it didn't match what the migration
said, and proposed a rename — one migration per app, matching exactly what
you saw.

Fix: added the *same* explicit `name=` already used in each migration file
directly to the corresponding `models.Index(...)` in models.py, so there's
no name left for Django to auto-generate or disagree about:

- `apps/users/models.py` — `users_user_email_idx`
- `apps/workspaces/models.py` — `workspaces_wm_ws_role_idx`
- `apps/projects/models.py` — `projects_ws_archived_idx`, `projects_pm_project_idx`

This should make `makemigrations --check --dry-run` report "No changes
detected." — but I can't confirm that without running it, so please verify
directly. If it still detects something, it means I got a name wrong
somewhere rather than this approach being unsound; paste the diff and I'll
match it exactly.

## 3. Only OWNER manages admins — extended to removal and invitation revocation

The Phase 3 correction round already made this rule for *sending* an
admin-role invitation (`only_owner_can_invite_admin`). Extended
consistently to two more places an ADMIN could otherwise act on a peer
ADMIN:

- **Removing a member**: `WorkspaceMemberDetailView.delete` now returns
  `403 only_owner_can_remove_admin` if the target is an ADMIN and the
  requester isn't the OWNER. ADMIN can still remove MEMBERs.
  Tests: `test_admin_cannot_remove_another_admin`,
  `test_owner_can_remove_an_admin` (`test_membership_roles.py`).
- **Revoking an invitation**: `WorkspaceInvitationRevokeView.delete` now
  returns `403 only_owner_can_revoke_admin_invitation` if the invitation's
  `intended_role` is ADMIN and the requester isn't the OWNER.
  Tests: `test_admin_cannot_revoke_admin_invitation`,
  `test_owner_can_revoke_admin_invitation` (`test_invitations.py`).

Also added, filling gaps rather than changing behavior — "safe"
acceptance/revocation for already-resolved invitations:
- `test_member_cannot_revoke_invitation` — a plain MEMBER couldn't revoke
  anything before either; there just wasn't a test proving it.
- `test_cannot_revoke_an_already_accepted_invitation` /
  `test_cannot_revoke_an_already_revoked_invitation` — revoking a
  non-pending invitation was already rejected (`not_pending`); now proven,
  including that an already-accepted membership survives untouched.
- `test_cannot_accept_an_already_accepted_invitation` — a second accept
  attempt with the same token was already impossible (the token stops
  resolving once status leaves PENDING) and doesn't create a duplicate
  membership; now proven explicitly rather than just implied by the
  resolver's filter.

## Changed files

```
README.md                                          new — Python version + setup
.python-version                                      new — "3.12"
manage.py                                             Python version guard
conftest.py                                            same guard (pytest bypasses manage.py)
requirements.txt                                        Python version comment
apps/users/models.py                                     explicit index name
apps/workspaces/models.py                                 explicit index name
apps/workspaces/views.py                                   admin-removal +
                                                              admin-invitation-revoke
                                                              restrictions
apps/projects/models.py                                     2 explicit index names
apps/workspaces/tests/test_membership_roles.py                +2 tests
apps/workspaces/tests/test_invitations.py                      +6 tests
```

Not touched: everything else from Phases 2–4, and `apps/projects/tests/*.py`'s
still-real-login `_login()` pattern (flagged again — same as last round;
say the word and I'll apply the `force_authenticate` fix there too).

## Remaining limitations

- Migration correctness for the four renamed indexes is my best-effort
  reasoning about *why* the mismatch happened, not something I've verified
  by actually running `makemigrations --check --dry-run` — please confirm.
- `apps/projects/tests/*.py` still hit the real login endpoint per test
  (same throttle-crash exposure fixed elsewhere last round) — not touched,
  per "do not start Phase 4."
- No activity logging on the two new permission denials (ADMIN blocked from
  removing an admin / revoking an admin invite) — `ActivityEvent` doesn't
  exist until Phase 7, same scope discipline as every prior phase.

Test count: **113 total** (105 + 8 new this round).
