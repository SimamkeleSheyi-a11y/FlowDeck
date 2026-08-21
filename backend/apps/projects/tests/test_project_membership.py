import pytest
from django.urls import reverse
from rest_framework import status

from apps.users.models import User
from apps.projects.models import Project, ProjectMembership
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
    """Force-authenticates without touching the real login endpoint — same
    fix applied to apps/workspaces/tests/* and apps/users/tests/test_profile.py."""
    api_client.force_authenticate(user=user)


@pytest.fixture
def workspace_owner_admin_member_project(api_client):
    owner = _make_user("pm_owner@example.com", "Owner")
    admin = _make_user("pm_admin@example.com", "Admin")
    member = _make_user("pm_member@example.com", "Member")
    _authenticate(api_client, owner)
    ws_created = api_client.post(reverse("workspaces:list-create"), {"name": "Membership Workspace"})
    workspace = Workspace.objects.get(id=ws_created.data["id"])
    WorkspaceMembership.objects.create(workspace=workspace, user=admin, role=WorkspaceRole.ADMIN)
    WorkspaceMembership.objects.create(workspace=workspace, user=member, role=WorkspaceRole.MEMBER)

    proj_created = api_client.post(
        reverse("projects:list-create"), {"workspace_id": str(workspace.id), "name": "Staffed Project"}
    )
    project = Project.objects.get(id=proj_created.data["id"])
    return workspace, project, owner, admin, member


def test_admin_can_add_a_workspace_member_to_the_project(api_client, workspace_owner_admin_member_project):
    workspace, project, _owner, admin, member = workspace_owner_admin_member_project
    _authenticate(api_client, admin)

    response = api_client.post(reverse("projects:members", args=[project.id]), {"user_id": str(member.id)})

    assert response.status_code == status.HTTP_201_CREATED
    assert ProjectMembership.objects.filter(project=project, user=member).exists()


def test_member_cannot_add_project_members(api_client, workspace_owner_admin_member_project):
    workspace, project, owner, _admin, member = workspace_owner_admin_member_project
    ProjectMembership.objects.create(project=project, user=member, added_by=owner)
    other = _make_user("pm_other@example.com", "Other")
    WorkspaceMembership.objects.create(workspace=workspace, user=other, role=WorkspaceRole.MEMBER)
    _authenticate(api_client, member)

    response = api_client.post(reverse("projects:members", args=[project.id]), {"user_id": str(other.id)})

    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_cannot_add_someone_outside_the_workspace_to_a_project(api_client, workspace_owner_admin_member_project):
    _workspace, project, owner, _admin, _member = workspace_owner_admin_member_project
    outsider = _make_user("pm_outsider@example.com", "Outsider")
    _authenticate(api_client, owner)

    response = api_client.post(reverse("projects:members", args=[project.id]), {"user_id": str(outsider.id)})

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["code"] == "not_workspace_member"
    assert ProjectMembership.objects.filter(project=project, user=outsider).exists() is False


def test_adding_the_same_member_twice_is_rejected(api_client, workspace_owner_admin_member_project):
    _workspace, project, owner, _admin, member = workspace_owner_admin_member_project
    _authenticate(api_client, owner)

    first = api_client.post(reverse("projects:members", args=[project.id]), {"user_id": str(member.id)})
    second = api_client.post(reverse("projects:members", args=[project.id]), {"user_id": str(member.id)})

    assert first.status_code == status.HTTP_201_CREATED
    assert second.status_code == status.HTTP_400_BAD_REQUEST
    assert second.data["code"] == "already_member"
    assert ProjectMembership.objects.filter(project=project, user=member).count() == 1


def test_owner_can_remove_a_project_member(api_client, workspace_owner_admin_member_project):
    _workspace, project, owner, _admin, member = workspace_owner_admin_member_project
    ProjectMembership.objects.create(project=project, user=member, added_by=owner)
    _authenticate(api_client, owner)

    response = api_client.delete(reverse("projects:member-detail", args=[project.id, member.id]))

    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert ProjectMembership.objects.filter(project=project, user=member).exists() is False


def test_member_cannot_remove_project_members(api_client, workspace_owner_admin_member_project):
    _workspace, project, owner, _admin, member = workspace_owner_admin_member_project
    ProjectMembership.objects.create(project=project, user=member, added_by=owner)
    _authenticate(api_client, member)

    response = api_client.delete(reverse("projects:member-detail", args=[project.id, member.id]))

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert ProjectMembership.objects.filter(project=project, user=member).exists()


def test_project_members_list_visible_to_anyone_with_project_access(api_client, workspace_owner_admin_member_project):
    _workspace, project, owner, _admin, member = workspace_owner_admin_member_project
    ProjectMembership.objects.create(project=project, user=member, added_by=owner)
    _authenticate(api_client, member)  # explicit member, not just implicit OWNER/ADMIN access

    response = api_client.get(reverse("projects:members", args=[project.id]))

    assert response.status_code == status.HTTP_200_OK
    assert len(response.data) == 1
    assert response.data[0]["user"]["email"] == member.email
