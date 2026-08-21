# Phase 6 corrections

Addresses the three issues raised before Phase 6 is accepted. No migrations
were changed, squashed, or added — none of these three fixes touch the
schema, only application-level logic and one new endpoint that reuses the
existing `position` column.

## Still true: I cannot run these commands here

Exactly the same constraint as every phase so far — no Django installed in
this sandbox, no network to install it. **I have not run**
`makemigrations --check --dry-run`, `migrate`, `check`, or `pytest -v`, and
I'm not fabricating output for any of them. Commands, unchanged:

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python manage.py makemigrations --check --dry-run
python manage.py migrate
python manage.py check
pytest -v
```

## Test count — computed from source, not from a run

**178 test *functions*, but 187 test *cases*** — the difference is
`test_phase6_permission_matrix.py`'s six `@pytest.mark.parametrize`d
functions, which pytest expands into 15 individual test IDs (9 "allowed"
cases × 3 roles + 6 "denied" cases × 2 roles) rather than 6. Breakdown:

- 159 existing (all preserved, none modified in a way that changes their
  outcome)
- +13 new non-parametrized functions (7 checklist-reorder, 6 label-validation)
- +15 new parametrized cases (from 6 parametrized function definitions)
- 159 + 13 + 15 = **187**

I'm flagging the def-vs-case distinction explicitly because "178" would be
a real but misleading answer to "exact final test count" if pytest's own
`-v` output is what you're comparing against — it'll show 187 collected
items, not 178.

## 1. Checklist-item reordering

New `POST /api/checklist-items/{item_id}/reorder/`, body
`{"after_item_id": null | "<uuid>"}`. Same gap-based midpoint scheme as
`BoardColumnReorderView` and `TaskMoveView` (`compute_checklist_item_position`
in `services.py`) — `null` places first, otherwise the item goes
immediately after `after_item_id` within the *same* checklist.

- Self-placement (`after_item_id == item_id`) → `400 invalid_position`.
- `after_item_id` from a different checklist → `400 invalid_after_item`
  (siblings are scoped to `item.checklist.items` only, so a foreign ID
  simply isn't found — this doesn't leak whether that ID exists elsewhere,
  same response either way).
- Cross-task/cross-project movement isn't just rejected, it's not an
  expressible request — the endpoint takes no target-checklist parameter
  at all, only a same-checklist sibling reference.
- Inaccessible items → `404`, via a new module-level
  `_get_visible_checklist_item_or_404` (previously a private method on
  `ChecklistItemDetailView`; refactored so both views share it rather than
  duplicating the IDOR check).

Tests (`test_checklists.py`): first/middle/last placement, self-placement,
cross-checklist `after_item_id`, MEMBER-with-membership access, non-member
404.

## 2. `LabelUpdateSerializer` validation

Two real gaps, both fixed:

- **Color wasn't validated on update at all.** `LabelCreateSerializer` used
  a `RegexField`; `LabelUpdateSerializer` (a `ModelSerializer`) just
  inherited the model field's bare `CharField(max_length=7)` — a PATCH
  could set a non-hex value with zero rejection. Added
  `validate_color` using the same `^#[0-9A-Fa-f]{6}$` pattern (factored
  into a shared `HEX_COLOR_RE` constant both serializers reference).
- **Renaming to a duplicate name wasn't checked at all** — the DB has a
  real `unique_label_name_per_project` constraint, so this would have
  surfaced as an uncaught `IntegrityError` (500), not a clean 400. Fixed in
  `LabelDetailView.patch`: checks `Label.objects.filter(project=..., 
  name__iexact=...).exclude(id=label.id).exists()` *before* calling
  `serializer.save()` — case-insensitive, excludes the label itself (so a
  no-op rename or a color-only edit that still sends the current name
  never spuriously fails), scoped to the project (the same name on a
  *different* project is unaffected — a different constraint pair
  entirely). Returns the same `{"detail", "code": "duplicate_label"}` shape
  the create path already used, for consistency.

Tests (`test_labels.py`): invalid color on create, invalid color on update,
valid color update accepted, case-insensitive duplicate rejected with the
original untouched, self-exclusion (re-saving the same name doesn't
false-positive), same name allowed across two different projects.

## 3. Phase 6 permission-matrix tests

New `test_phase6_permission_matrix.py`, one shared fixture (OWNER, ADMIN
with no `ProjectMembership` row, a MEMBER *with* one, a MEMBER *without*
one, and a total outsider), parametrized across all three Phase 6 feature
areas — assignment, label creation, checklist-item creation:

| Actor | Expected |
|---|---|
| OWNER | allowed |
| ADMIN (implicit access, Section 6.1) | allowed |
| MEMBER with `ProjectMembership` | allowed |
| MEMBER without `ProjectMembership` | 404 |
| outsider (not a workspace member) | 404 |

This is a dedicated matrix check on top of the per-feature tests already in
`test_task_assignees.py`/`test_labels.py`/`test_checklists.py`, which cover
individual behaviors in depth but weren't testing the role matrix
explicitly across all three features side by side.

## Files changed — no migrations touched

```
apps/tasks/services.py                     +compute_checklist_item_position
apps/tasks/serializers.py                    +ChecklistItemReorderSerializer,
                                                HEX_COLOR_RE constant,
                                                LabelUpdateSerializer.validate_color
apps/tasks/views.py                            +ChecklistItemReorderView,
                                                  LabelDetailView.patch duplicate check,
                                                  _get_visible_checklist_item_or_404
                                                  promoted to module level
apps/tasks/urls.py                               +1 route
apps/tasks/tests/test_checklists.py                +7 tests
apps/tasks/tests/test_labels.py                      +6 tests
apps/tasks/tests/test_phase6_permission_matrix.py      new — 6 functions / 15 cases
```

Not touched: every migration file, every model, and all four other
already-existing apps.

Test count: **187** (159 preserved + 28 new: 13 functions + 15 parametrized cases).
