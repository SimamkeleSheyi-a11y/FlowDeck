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
    """
    Force-authenticates the test client as `user` without touching the real
    login endpoint. This suite tests workspace behavior, not login itself —
    hitting /api/auth/login/ once per test was tripping the real 10/minute
    login throttle once the full suite ran together, which is a test
    isolation bug, not something login-specific tests should be weakened to
    accommodate. See apps/users/tests/test_login_logout.py for the tests
    that actually exercise the real login endpoint.
    """
    api_client.force_authenticate(user=user)


def test_create_workspace_makes_creator_owner(api_client):
    user = _make_user("owner@example.com", "Owner")
    _authenticate(api_client, user)

    response = api_client.post(reverse("workspaces:list-create"), {"name": "FlowDeck HQ", "description": "Main workspace"})

    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["my_role"] == WorkspaceRole.OWNER
    workspace = Workspace.objects.get(id=response.data["id"])
    membership = WorkspaceMembership.objects.get(workspace=workspace, user=user)
    assert membership.role == WorkspaceRole.OWNER


def test_workspace_gets_a_unique_slug(api_client):
    user = _make_user("slug@example.com", "Slug Test")
    _authenticate(api_client, user)

    first = api_client.post(reverse("workspaces:list-create"), {"name": "Acme Team"})
    second = api_client.post(reverse("workspaces:list-create"), {"name": "Acme Team"})

    assert first.data["slug"] != second.data["slug"]
    assert first.data["slug"] == "acme-team"
    assert second.data["slug"] == "acme-team-2"


def test_list_workspaces_only_shows_own(api_client):
    owner = _make_user("listowner@example.com", "List Owner")
    outsider = _make_user("outsider@example.com", "Outsider")
    _authenticate(api_client, owner)
    api_client.post(reverse("workspaces:list-create"), {"name": "Private Space"})

    api_client.credentials()
    _authenticate(api_client, outsider)
    response = api_client.get(reverse("workspaces:list-create"))

    assert response.status_code == status.HTTP_200_OK
    assert response.data["results"] == []
    assert response.data["count"] == 0


def test_non_member_gets_404_not_403(api_client):
    owner = _make_user("hidden_owner@example.com", "Hidden Owner")
    outsider = _make_user("uninvited@example.com", "Uninvited")
    _authenticate(api_client, owner)
    created = api_client.post(reverse("workspaces:list-create"), {"name": "Secret Project"})
    workspace_id = created.data["id"]

    api_client.credentials()
    _authenticate(api_client, outsider)
    response = api_client.get(reverse("workspaces:detail", args=[workspace_id]))

    # Deliberately 404, not 403 — existence of the workspace is itself
    # invisible to non-members (Phase 1 architecture doc, Section 11).
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_owner_can_update_workspace(api_client):
    owner = _make_user("editor_owner@example.com", "Editor Owner")
    _authenticate(api_client, owner)
    created = api_client.post(reverse("workspaces:list-create"), {"name": "Original Name"})

    response = api_client.patch(reverse("workspaces:detail", args=[created.data["id"]]), {"name": "Renamed"})

    assert response.status_code == status.HTTP_200_OK
    assert response.data["name"] == "Renamed"


def test_member_cannot_update_or_delete_workspace(api_client):
    owner = _make_user("memberperm_owner@example.com", "Owner")
    member = _make_user("memberperm_member@example.com", "Member")
    _authenticate(api_client, owner)
    created = api_client.post(reverse("workspaces:list-create"), {"name": "Team Space"})
    workspace_id = created.data["id"]
    workspace = Workspace.objects.get(id=workspace_id)
    WorkspaceMembership.objects.create(workspace=workspace, user=member, role=WorkspaceRole.MEMBER)

    api_client.credentials()
    _authenticate(api_client, member)

    patch_response = api_client.patch(reverse("workspaces:detail", args=[workspace_id]), {"name": "Hijacked"})
    delete_response = api_client.delete(reverse("workspaces:detail", args=[workspace_id]))

    assert patch_response.status_code == status.HTTP_403_FORBIDDEN
    assert delete_response.status_code == status.HTTP_403_FORBIDDEN


def test_only_owner_can_delete_workspace(api_client):
    owner = _make_user("deleter_owner@example.com", "Owner")
    admin = _make_user("deleter_admin@example.com", "Admin")
    _authenticate(api_client, owner)
    created = api_client.post(reverse("workspaces:list-create"), {"name": "Doomed Workspace"})
    workspace_id = created.data["id"]
    workspace = Workspace.objects.get(id=workspace_id)
    WorkspaceMembership.objects.create(workspace=workspace, user=admin, role=WorkspaceRole.ADMIN)

    api_client.credentials()
    _authenticate(api_client, admin)
    admin_delete = api_client.delete(reverse("workspaces:detail", args=[workspace_id]))
    assert admin_delete.status_code == status.HTTP_403_FORBIDDEN

    api_client.credentials()
    _authenticate(api_client, owner)
    owner_delete = api_client.delete(reverse("workspaces:detail", args=[workspace_id]))
    assert owner_delete.status_code == status.HTTP_204_NO_CONTENT
    assert Workspace.objects.filter(id=workspace_id).exists() is False


def test_unverified_user_cannot_create_workspace(api_client):
    user = _make_user("unverified@example.com", "Unverified", verified=False)
    _authenticate(api_client, user)

    response = api_client.post(reverse("workspaces:list-create"), {"name": "Should Not Exist"})

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert Workspace.objects.filter(name="Should Not Exist").exists() is False


def test_workspace_list_is_paginated(api_client):
    user = _make_user("paginated@example.com", "Paginator")
    _authenticate(api_client, user)
    for i in range(3):
        api_client.post(reverse("workspaces:list-create"), {"name": f"Workspace {i}"})

    response = api_client.get(reverse("workspaces:list-create"))

    assert response.status_code == status.HTTP_200_OK
    assert set(response.data.keys()) == {"count", "next", "previous", "results"}
    assert response.data["count"] == 3
    assert len(response.data["results"]) == 3


def test_workspace_list_does_not_grow_queries_with_workspace_count(api_client, django_assert_max_num_queries):
    user = _make_user("queries@example.com", "Query Counter")
    _authenticate(api_client, user)
    for i in range(8):
        api_client.post(reverse("workspaces:list-create"), {"name": f"Query Workspace {i}"})

    # A handful of fixed queries (auth lookup, pagination count, the
    # workspace select, the prefetch of just-this-user's memberships)
    # regardless of how many workspaces are being listed — NOT one extra
    # query per workspace for `my_role`, which is the N+1 this guards
    # against. 8 workspaces would blow well past this bound if the N+1
    # regressed.
    with django_assert_max_num_queries(10):
        response = api_client.get(reverse("workspaces:list-create"))

    assert response.status_code == status.HTTP_200_OK
    assert response.data["count"] == 8
    for item in response.data["results"]:
        assert item["my_role"] == WorkspaceRole.OWNER
