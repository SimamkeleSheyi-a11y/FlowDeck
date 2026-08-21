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
    """
    A workspace with OWNER, ADMIN, and MEMBER, plus one project that only
    the OWNER explicitly belongs to (no ProjectMembership for admin/member)
    — set up this way specifically to exercise the Section 6.1 rule.
    """
    owner = _make_user("vis_owner@example.com", "Owner")
    admin = _make_user("vis_admin@example.com", "Admin")
    member = _make_user("vis_member@example.com", "Member")
    _authenticate(api_client, owner)
    ws_created = api_client.post(reverse("workspaces:list-create"), {"name": "Visibility Workspace"})
    workspace = Workspace.objects.get(id=ws_created.data["id"])
    WorkspaceMembership.objects.create(workspace=workspace, user=admin, role=WorkspaceRole.ADMIN)
    WorkspaceMembership.objects.create(workspace=workspace, user=member, role=WorkspaceRole.MEMBER)

    proj_created = api_client.post(
        reverse("projects:list-create"), {"workspace_id": str(workspace.id), "name": "Team Project"}
    )
    project = Project.objects.get(id=proj_created.data["id"])
    return workspace, project, owner, admin, member


def test_owner_can_view_project_without_explicit_membership(api_client, workspace_owner_admin_member_project):
    _workspace, project, owner, _admin, _member = workspace_owner_admin_member_project
    _authenticate(api_client, owner)

    response = api_client.get(reverse("projects:detail", args=[project.id]))

    assert response.status_code == status.HTTP_200_OK
    assert response.data["am_i_a_project_member"] is False  # implicit access, not explicit membership


def test_admin_can_view_project_without_explicit_membership(api_client, workspace_owner_admin_member_project):
    _workspace, project, _owner, admin, _member = workspace_owner_admin_member_project
    _authenticate(api_client, admin)

    response = api_client.get(reverse("projects:detail", args=[project.id]))

    assert response.status_code == status.HTTP_200_OK
    assert response.data["am_i_a_project_member"] is False


def test_member_without_project_membership_gets_404(api_client, workspace_owner_admin_member_project):
    _workspace, project, _owner, _admin, member = workspace_owner_admin_member_project
    _authenticate(api_client, member)

    response = api_client.get(reverse("projects:detail", args=[project.id]))

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_member_with_explicit_membership_can_view(api_client, workspace_owner_admin_member_project):
    _workspace, project, owner, _admin, member = workspace_owner_admin_member_project
    ProjectMembership.objects.create(project=project, user=member, added_by=owner)
    _authenticate(api_client, member)

    response = api_client.get(reverse("projects:detail", args=[project.id]))

    assert response.status_code == status.HTTP_200_OK
    assert response.data["am_i_a_project_member"] is True


def test_user_from_a_different_workspace_gets_404_not_403(api_client, workspace_owner_admin_member_project):
    _workspace, project, _owner, _admin, _member = workspace_owner_admin_member_project
    stranger = _make_user("vis_stranger@example.com", "Stranger")
    _authenticate(api_client, stranger)

    response = api_client.get(reverse("projects:detail", args=[project.id]))

    # Existence hidden from someone with no relationship to the workspace at
    # all — same IDOR policy as the workspace endpoints (Phase 1 doc,
    # Section 11).
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_member_project_appears_in_their_project_list(api_client, workspace_owner_admin_member_project):
    _workspace, project, owner, _admin, member = workspace_owner_admin_member_project
    ProjectMembership.objects.create(project=project, user=member, added_by=owner)
    _authenticate(api_client, member)

    response = api_client.get(reverse("projects:list-create"))

    assert response.status_code == status.HTTP_200_OK
    assert response.data["count"] == 1
    assert response.data["results"][0]["id"] == str(project.id)


def test_member_without_membership_sees_no_projects_in_list(api_client, workspace_owner_admin_member_project):
    _workspace, _project, _owner, _admin, member = workspace_owner_admin_member_project
    _authenticate(api_client, member)

    response = api_client.get(reverse("projects:list-create"))

    assert response.status_code == status.HTTP_200_OK
    assert response.data["count"] == 0
