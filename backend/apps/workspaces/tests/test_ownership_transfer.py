from unittest.mock import patch

import pytest
from django.urls import reverse
from rest_framework import status

from apps.users.models import User
from apps.workspaces.models import Workspace, WorkspaceMembership, WorkspaceRole

pytestmark = pytest.mark.django_db

PASSWORD = "TestPass123!"


def _make_user(email, display_name, verified=True):
    user = User.objects.create_user(email=email, password=PASSWORD, display_name=display_name)
    if verified:
        user.is_email_verified = True
        user.save(update_fields=["is_email_verified"])
    return user


def _authenticate(api_client, user):
    """Force-authenticates without touching the real login endpoint — see
    test_workspace_crud.py's _authenticate() for the full rationale."""
    api_client.force_authenticate(user=user)


@pytest.fixture
def workspace_with_owner_and_member(api_client):
    owner = _make_user("transfer_owner@example.com", "Owner")
    member = _make_user("transfer_member@example.com", "Member")
    _authenticate(api_client, owner)
    created = api_client.post(reverse("workspaces:list-create"), {"name": "Transfer Workspace"})
    workspace = Workspace.objects.get(id=created.data["id"])
    WorkspaceMembership.objects.create(workspace=workspace, user=member, role=WorkspaceRole.MEMBER)
    return workspace, owner, member


def test_owner_can_transfer_ownership_to_existing_member(api_client, workspace_with_owner_and_member):
    workspace, owner, member = workspace_with_owner_and_member
    _authenticate(api_client, owner)

    response = api_client.post(
        reverse("workspaces:ownership-transfer", args=[workspace.id]), {"user_id": str(member.id)}
    )

    assert response.status_code == status.HTTP_200_OK
    owner_membership = WorkspaceMembership.objects.get(workspace=workspace, user=owner)
    member_membership = WorkspaceMembership.objects.get(workspace=workspace, user=member)
    assert owner_membership.role == WorkspaceRole.ADMIN
    assert member_membership.role == WorkspaceRole.OWNER

    # exactly one OWNER row must exist at all times — the DB constraint
    # (and the transfer logic) must never leave this workspace with 0 or 2
    assert WorkspaceMembership.objects.filter(workspace=workspace, role=WorkspaceRole.OWNER).count() == 1


def test_non_owner_cannot_transfer_ownership(api_client, workspace_with_owner_and_member):
    workspace, _owner, member = workspace_with_owner_and_member
    _authenticate(api_client, member)

    response = api_client.post(
        reverse("workspaces:ownership-transfer", args=[workspace.id]), {"user_id": str(member.id)}
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_cannot_transfer_ownership_to_a_non_member(api_client, workspace_with_owner_and_member):
    workspace, owner, _member = workspace_with_owner_and_member
    outsider = _make_user("transfer_outsider@example.com", "Outsider")
    _authenticate(api_client, owner)

    response = api_client.post(
        reverse("workspaces:ownership-transfer", args=[workspace.id]), {"user_id": str(outsider.id)}
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert WorkspaceMembership.objects.get(workspace=workspace, user=owner).role == WorkspaceRole.OWNER


def test_cannot_transfer_ownership_to_self(api_client, workspace_with_owner_and_member):
    workspace, owner, _member = workspace_with_owner_and_member
    _authenticate(api_client, owner)

    response = api_client.post(
        reverse("workspaces:ownership-transfer", args=[workspace.id]), {"user_id": str(owner.id)}
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_ownership_transfer_rechecks_after_lock_and_detects_a_stale_precondition(
    api_client, workspace_with_owner_and_member
):
    """
    Simulates a race: the outer, pre-lock permission check believes the
    requester is still OWNER, but the database's real state has already
    changed underneath by the time the locked re-check inside the
    transaction actually runs. This proves it's the re-check — not just the
    earlier permission check — that guards correctness.

    Real concurrent-thread testing (two DB connections racing for the same
    lock) isn't attempted here — that needs pytest-django's
    `transactional_db` fixture plus real threads against a backend that
    supports row locking (Postgres, not the sqlite this suite runs
    against), and hasn't been exercised in this sandbox. This test instead
    proves the re-check logic itself is correct by forcing the exact stale
    state a real race would produce, via a mocked outer check.
    """
    workspace, owner, member = workspace_with_owner_and_member
    other_member = _make_user("transfer_other@example.com", "Other Member")
    WorkspaceMembership.objects.create(workspace=workspace, user=other_member, role=WorkspaceRole.MEMBER)

    # Ownership has *actually* already moved to `member` in the database...
    WorkspaceMembership.objects.filter(workspace=workspace, user=owner).update(role=WorkspaceRole.ADMIN)
    WorkspaceMembership.objects.filter(workspace=workspace, user=member).update(role=WorkspaceRole.OWNER)

    _authenticate(api_client, owner)

    # ...but the outer, pre-lock permission check is patched to still see
    # `owner` as OWNER — standing in for "this read happened a moment
    # before a concurrent transfer committed."
    stale_membership = WorkspaceMembership(workspace=workspace, user=owner, role=WorkspaceRole.OWNER)
    with patch("apps.workspaces.views.get_membership", return_value=stale_membership):
        response = api_client.post(
            reverse("workspaces:ownership-transfer", args=[workspace.id]),
            {"user_id": str(other_member.id)},
        )

    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.data["code"] == "ownership_changed"

    # the real, already-committed transfer to `member` must be untouched
    assert WorkspaceMembership.objects.get(workspace=workspace, user=member).role == WorkspaceRole.OWNER
    assert WorkspaceMembership.objects.filter(workspace=workspace, role=WorkspaceRole.OWNER).count() == 1
