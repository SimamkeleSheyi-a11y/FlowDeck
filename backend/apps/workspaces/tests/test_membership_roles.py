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
def workspace_with_roles(api_client):
    owner = _make_user("roles_owner@example.com", "Owner")
    admin = _make_user("roles_admin@example.com", "Admin")
    member = _make_user("roles_member@example.com", "Member")

    _authenticate(api_client, owner)
    created = api_client.post(reverse("workspaces:list-create"), {"name": "Roles Workspace"})
    workspace = Workspace.objects.get(id=created.data["id"])
    WorkspaceMembership.objects.create(workspace=workspace, user=admin, role=WorkspaceRole.ADMIN)
    WorkspaceMembership.objects.create(workspace=workspace, user=member, role=WorkspaceRole.MEMBER)

    return workspace, owner, admin, member


def test_owner_can_promote_member_to_admin(api_client, workspace_with_roles):
    workspace, owner, _admin, member = workspace_with_roles
    _authenticate(api_client, owner)

    response = api_client.patch(
        reverse("workspaces:member-detail", args=[workspace.id, member.id]), {"role": "ADMIN"}
    )

    assert response.status_code == status.HTTP_200_OK
    assert WorkspaceMembership.objects.get(workspace=workspace, user=member).role == WorkspaceRole.ADMIN


def test_admin_cannot_change_roles(api_client, workspace_with_roles):
    workspace, _owner, admin, member = workspace_with_roles
    _authenticate(api_client, admin)

    response = api_client.patch(
        reverse("workspaces:member-detail", args=[workspace.id, member.id]), {"role": "ADMIN"}
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_cannot_patch_owner_role_via_member_endpoint(api_client, workspace_with_roles):
    workspace, owner, _admin, _member = workspace_with_roles
    _authenticate(api_client, owner)

    response = api_client.patch(
        reverse("workspaces:member-detail", args=[workspace.id, owner.id]), {"role": "ADMIN"}
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert WorkspaceMembership.objects.get(workspace=workspace, user=owner).role == WorkspaceRole.OWNER


def test_role_update_rejects_owner_as_a_choice(api_client, workspace_with_roles):
    workspace, owner, _admin, member = workspace_with_roles
    _authenticate(api_client, owner)

    response = api_client.patch(
        reverse("workspaces:member-detail", args=[workspace.id, member.id]), {"role": "OWNER"}
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_admin_can_remove_a_member(api_client, workspace_with_roles):
    workspace, _owner, admin, member = workspace_with_roles
    _authenticate(api_client, admin)

    response = api_client.delete(reverse("workspaces:member-detail", args=[workspace.id, member.id]))

    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert WorkspaceMembership.objects.filter(workspace=workspace, user=member).exists() is False


def test_member_cannot_remove_anyone(api_client, workspace_with_roles):
    workspace, _owner, admin, member = workspace_with_roles
    _authenticate(api_client, member)

    response = api_client.delete(reverse("workspaces:member-detail", args=[workspace.id, admin.id]))

    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_owner_cannot_be_removed_via_member_endpoint(api_client, workspace_with_roles):
    workspace, owner, admin, _member = workspace_with_roles
    _authenticate(api_client, admin)

    response = api_client.delete(reverse("workspaces:member-detail", args=[workspace.id, owner.id]))

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert WorkspaceMembership.objects.filter(workspace=workspace, user=owner).exists()


def test_removing_yourself_via_member_endpoint_is_rejected(api_client, workspace_with_roles):
    workspace, _owner, admin, _member = workspace_with_roles
    _authenticate(api_client, admin)

    response = api_client.delete(reverse("workspaces:member-detail", args=[workspace.id, admin.id]))

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["code"] == "use_leave_endpoint"


def test_member_can_leave_workspace(api_client, workspace_with_roles):
    workspace, _owner, _admin, member = workspace_with_roles
    _authenticate(api_client, member)

    response = api_client.post(reverse("workspaces:leave", args=[workspace.id]))

    assert response.status_code == status.HTTP_200_OK
    assert WorkspaceMembership.objects.filter(workspace=workspace, user=member).exists() is False


def test_owner_cannot_leave_without_transferring_first(api_client, workspace_with_roles):
    workspace, owner, _admin, _member = workspace_with_roles
    _authenticate(api_client, owner)

    response = api_client.post(reverse("workspaces:leave", args=[workspace.id]))

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert WorkspaceMembership.objects.filter(workspace=workspace, user=owner, role=WorkspaceRole.OWNER).exists()


def test_admin_cannot_remove_another_admin(api_client, workspace_with_roles):
    workspace, _owner, admin, _member = workspace_with_roles
    second_admin = _make_user("roles_admin2@example.com", "Second Admin")
    WorkspaceMembership.objects.create(workspace=workspace, user=second_admin, role=WorkspaceRole.ADMIN)
    _authenticate(api_client, admin)

    response = api_client.delete(reverse("workspaces:member-detail", args=[workspace.id, second_admin.id]))

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.data["code"] == "only_owner_can_remove_admin"
    assert WorkspaceMembership.objects.filter(workspace=workspace, user=second_admin).exists()


def test_owner_can_remove_an_admin(api_client, workspace_with_roles):
    workspace, owner, admin, _member = workspace_with_roles
    _authenticate(api_client, owner)

    response = api_client.delete(reverse("workspaces:member-detail", args=[workspace.id, admin.id]))

    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert WorkspaceMembership.objects.filter(workspace=workspace, user=admin).exists() is False
