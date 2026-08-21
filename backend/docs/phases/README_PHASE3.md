# FlowDeck Backend — Phase 3 corrections

This documents the correction pass requested after the initial Phase 3 pass:
workspaces, memberships, roles, and invitations, with the seven fixes below
applied on top of what was already built.

## Has this actually been run?

**No — same constraint as Phases 2 and 3, unchanged.** This sandbox still
has no Django installed and no network access to install it (`pip install
django` / `apt-get update` both still fail — nothing about that has changed
since it was first flagged). So, same as before:

- **Migrations are hand-authored, not machine-generated.** I cannot run
  `makemigrations`. I wrote `apps/users/migrations/0001_initial.py` and
  `apps/workspaces/migrations/0001_initial.py` by hand, matching the models
  as closely as I can. They should be *functionally* correct — creating the
  right tables/columns/constraints — but I cannot guarantee they're
  byte-identical to what Django's autodetector would produce (cosmetic
  things like auto-generated index-name hashes, in particular). **The
  single most important thing to do before trusting these**:
  ```bash
  python manage.py makemigrations --check --dry-run
  ```
  If Django says no changes are needed, these files are confirmed correct.
  If it wants to add something, trust Django's autodetector over my hand-
  written files and let it generate the difference.
- **The test suite has not been executed.** 77 tests now exist (10 net new
  this pass). All 60 `.py` files in the repo pass `python -m py_compile` —
  syntax-valid, nothing more. I have not run `pytest` and am not claiming
  any test "passes" — that can only be confirmed by actually running it.

I know this isn't what was asked for ("then run the full test suite") — I
can't do that here, and I'd rather say so plainly than report results I
didn't produce. Running `pytest -v` after `pip install -r requirements.txt`
and `migrate` is the fastest way to get a real, trustworthy answer — happy
to fix anything that comes back failing.

## The seven fixes

1. **Migrations** — see above. `apps/users/migrations/0001_initial.py`
   (new), `apps/workspaces/migrations/0001_initial.py` (new, folds in the
   `token_hash` uniqueness fix from #6 directly rather than as a follow-up
   migration, since nothing has ever actually been deployed against the
   earlier version of that field).

2. **ADMIN can invite MEMBER but not ADMIN** —
   `WorkspaceInvitationListCreateView.post` now rejects (403,
   `only_owner_can_invite_admin`) an ADMIN trying to send an
   `intended_role=ADMIN` invitation; only OWNER can. Regression tests:
   `test_admin_can_invite_member`, `test_admin_cannot_invite_admin`,
   `test_owner_can_invite_admin` in `test_invitations.py`.

3. **Expired invitations no longer block reinviting** — new
   `services.expire_stale_invitations()` bulk-flips any `PENDING`
   invitation whose `expires_at` has passed to `EXPIRED`. Called before the
   duplicate-pending check in `WorkspaceInvitationListCreateView.post` and
   before listing in `.get`. Regression test:
   `test_expired_invitation_flips_to_expired_and_unblocks_reinvite`.

4. **N+1 removed from the workspace list + pagination added** —
   `WorkspaceListCreateView.get` now uses `Prefetch("memberships",
   queryset=<just-this-user's-memberships>, to_attr="my_memberships")`
   instead of `WorkspaceSerializer.get_my_role` querying per object, and
   wraps the response in `LimitOffsetPagination` (the
   `DEFAULT_PAGINATION_CLASS` already configured in settings, reused rather
   than introducing something new). Regression tests:
   `test_workspace_list_is_paginated`,
   `test_workspace_list_does_not_grow_queries_with_workspace_count` (uses
   pytest-django's `django_assert_max_num_queries` to bound the query count
   regardless of workspace count).

5. **Verified email required for workspace functionality** — every
   authenticated workspace/invitation view now uses
   `[IsAuthenticated, IsEmailVerified]` (the `IsEmailVerified` class already
   written in Phase 2, now actually wired up). The one exception is
   `InvitationPreviewView`, which is intentionally unauthenticated — there's
   no user to verify yet. **Scope decision worth flagging**: I interpreted
   "workspace functionality" broadly — this blocks an unverified user from
   *everything* workspace-related, including just viewing a workspace they
   already belong to, not only creation/invitation actions. If you'd rather
   scope it narrower (e.g. only create/invite/accept), that's a small
   change to `WORKSPACE_PERMISSIONS` usage per-view. All existing workspace
   test fixtures now create verified users by default (`_make_user(...,
   verified=True)`); new regression tests explicitly cover the unverified
   case: `test_unverified_user_cannot_create_workspace`,
   `test_unverified_invitee_cannot_accept`.

6. **O(n) invitation-token scan replaced with a direct hash lookup** —
   `WorkspaceInvitation.token_hash` is now `unique=True` (indexed);
   `services.resolve_invitation_by_raw_token` does a direct
   `.filter(token_hash=..., status=PENDING, expires_at__gt=now).first()`
   instead of iterating every pending invitation and comparing hashes one
   at a time. The now-unused constant-time `check_token()` method was
   removed from the model along with the `secrets` import it needed — a
   DB-indexed equality lookup on a *hash* doesn't have the timing-attack
   exposure that comparing a raw secret byte-by-byte would. Regression
   test: `test_resolving_a_token_does_not_scan_every_pending_invitation`
   (creates 20 decoy pending invitations, asserts resolving the real one
   stays within a small fixed query budget).

7. **Ownership transfer is now concurrency-safe** —
   `OwnershipTransferView.post` re-reads the current owner and target
   membership *inside* the transaction, using `select_for_update()` where
   the database backend supports row locking (real locking on Postgres;
   SQLite doesn't support `SELECT ... FOR UPDATE` at all, so the code
   checks `connection.features.has_select_for_update` and only applies it
   there), then re-verifies both preconditions before writing. If the
   requester is no longer OWNER, or the target is no longer a member, or
   the target is already OWNER, it returns `409 CONFLICT`
   (`ownership_changed`) instead of corrupting state. **Honest limitation**:
   genuine concurrent-thread testing (two real DB connections racing for
   the same lock) needs pytest-django's `transactional_db` fixture plus
   actual threads against a backend that supports locking — not attempted
   here. Instead, `test_ownership_transfer_rechecks_after_lock_and_detects_a_stale_precondition`
   proves the re-check logic itself is correct by mocking the outer
   permission check to return a stale result while the real database has
   already moved — the same failure mode a genuine race would produce.

## Files changed this pass

```
apps/users/migrations/0001_initial.py         new
apps/workspaces/migrations/0001_initial.py     new
apps/workspaces/models.py                       token_hash unique=True; removed check_token()
apps/workspaces/services.py                      expire_stale_invitations(); direct hash lookup
apps/workspaces/views.py                          IsEmailVerified everywhere but preview; pagination
                                                    + prefetch fix on list; admin-can't-invite-admin;
                                                    expiry sweep before duplicate check; locked +
                                                    rechecked ownership transfer
apps/workspaces/serializers.py                     get_my_role reads the prefetched attr when present
apps/workspaces/tests/test_workspace_crud.py        verified-by-default helper; +3 tests
apps/workspaces/tests/test_membership_roles.py       verified-by-default helper
apps/workspaces/tests/test_ownership_transfer.py      verified-by-default helper; +1 test
apps/workspaces/tests/test_invitations.py              verified-by-default helper; new
                                                          owner/admin/member fixture; +6 tests
```

**Preserved, untouched**: everything from Phase 2 (`apps/users/`), and every
workspace behavior from the first Phase 3 pass that wasn't part of this
correction list — CRUD permissions, leave-workspace rules, member
removal/role-change rules, the 404-not-403 IDOR scoping, invitation
send/preview/accept/revoke happy paths.

## Test count

77 total (was 67): 36 in `apps/users/`, 41 in `apps/workspaces/` (31 + 10
net new this pass).
