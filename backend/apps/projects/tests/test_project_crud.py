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
def workspace_with_roles(api_client):
    owner = _make_user("proj_owner@example.com", "Owner")
    admin = _make_user("proj_admin@example.com", "Admin")
    member = _make_user("proj_member@example.com", "Member")
    _authenticate(api_client, owner)
    created = api_client.post(reverse("workspaces:list-create"), {"name": "Project Test Workspace"})
    workspace = Workspace.objects.get(id=created.data["id"])
    WorkspaceMembership.objects.create(workspace=workspace, user=admin, role=WorkspaceRole.ADMIN)
    WorkspaceMembership.objects.create(workspace=workspace, user=member, role=WorkspaceRole.MEMBER)
    return workspace, owner, admin, member


def test_owner_can_create_project(api_client, workspace_with_roles):
    workspace, owner, _admin, _member = workspace_with_roles
    _authenticate(api_client, owner)

    response = api_client.post(
        reverse("projects:list-create"),
        {"workspace_id": str(workspace.id), "name": "Website Redesign", "description": "Q3 revamp"},
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["name"] == "Website Redesign"
    assert response.data["workspace_id"] == str(workspace.id)
    project = Project.objects.get(id=response.data["id"])
    assert project.created_by == owner


def test_admin_can_create_project(api_client, workspace_with_roles):
    workspace, _owner, admin, _member = workspace_with_roles
    _authenticate(api_client, admin)

    response = api_client.post(
        reverse("projects:list-create"), {"workspace_id": str(workspace.id), "name": "Admin's Project"}
    )

    assert response.status_code == status.HTTP_201_CREATED


def test_member_cannot_create_project(api_client, workspace_with_roles):
    workspace, _owner, _admin, member = workspace_with_roles
    _authenticate(api_client, member)

    response = api_client.post(
        reverse("projects:list-create"), {"workspace_id": str(workspace.id), "name": "Should Fail"}
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert Project.objects.filter(name="Should Fail").exists() is False


def test_cannot_create_project_in_a_workspace_you_do_not_belong_to(api_client, workspace_with_roles):
    workspace, _owner, _admin, _member = workspace_with_roles
    outsider = _make_user("proj_outsider@example.com", "Outsider")
    _authenticate(api_client, outsider)

    response = api_client.post(
        reverse("projects:list-create"), {"workspace_id": str(workspace.id), "name": "Sneaky Project"}
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert Project.objects.filter(name="Sneaky Project").exists() is False


def test_unverified_user_cannot_create_project(api_client, workspace_with_roles):
    workspace, owner, _admin, _member = workspace_with_roles
    unverified = _make_user("proj_unverified@example.com", "Unverified", verified=False)
    WorkspaceMembership.objects.create(workspace=workspace, user=unverified, role=WorkspaceRole.ADMIN)
    _authenticate(api_client, unverified)

    response = api_client.post(
        reverse("projects:list-create"), {"workspace_id": str(workspace.id), "name": "Blocked Project"}
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_owner_can_update_and_archive_project(api_client, workspace_with_roles):
    workspace, owner, _admin, _member = workspace_with_roles
    _authenticate(api_client, owner)
    created = api_client.post(
        reverse("projects:list-create"), {"workspace_id": str(workspace.id), "name": "Original"}
    )
    project_id = created.data["id"]

    patch_response = api_client.patch(reverse("projects:detail", args=[project_id]), {"name": "Renamed"})
    assert patch_response.status_code == status.HTTP_200_OK
    assert patch_response.data["name"] == "Renamed"

    archive_response = api_client.post(reverse("projects:archive", args=[project_id]))
    assert archive_response.status_code == status.HTTP_200_OK
    assert archive_response.data["archived_at"] is not None

    unarchive_response = api_client.post(reverse("projects:unarchive", args=[project_id]))
    assert unarchive_response.status_code == status.HTTP_200_OK
    assert unarchive_response.data["archived_at"] is None


def test_member_cannot_update_archive_or_delete_project(api_client, workspace_with_roles):
    workspace, owner, _admin, member = workspace_with_roles
    _authenticate(api_client, owner)
    created = api_client.post(
        reverse("projects:list-create"), {"workspace_id": str(workspace.id), "name": "Guarded Project"}
    )
    project_id = created.data["id"]
    # This test is about role permission (a project MEMBER can't manage the
    # project), not project visibility — give the member explicit
    # ProjectMembership first so they can see the project at all. Without
    # this, the correct response is 404 (can't discover the project), not
    # 403 — a different, already separately-tested behavior
    # (test_non_member_gets_404_not_403).
    ProjectMembership.objects.create(project_id=project_id, user=member, added_by=owner)

    api_client.credentials()
    _authenticate(api_client, member)

    assert api_client.patch(reverse("projects:detail", args=[project_id]), {"name": "Hijack"}).status_code == status.HTTP_403_FORBIDDEN
    assert api_client.post(reverse("projects:archive", args=[project_id])).status_code == status.HTTP_403_FORBIDDEN
    assert api_client.delete(reverse("projects:detail", args=[project_id])).status_code == status.HTTP_403_FORBIDDEN


def test_owner_can_delete_project(api_client, workspace_with_roles):
    workspace, owner, _admin, _member = workspace_with_roles
    _authenticate(api_client, owner)
    created = api_client.post(
        reverse("projects:list-create"), {"workspace_id": str(workspace.id), "name": "Doomed Project"}
    )
    project_id = created.data["id"]

    response = api_client.delete(reverse("projects:detail", args=[project_id]))

    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert Project.objects.filter(id=project_id).exists() is False


def test_archived_projects_excluded_from_default_list(api_client, workspace_with_roles):
    workspace, owner, _admin, _member = workspace_with_roles
    _authenticate(api_client, owner)
    created = api_client.post(
        reverse("projects:list-create"), {"workspace_id": str(workspace.id), "name": "Will Archive"}
    )
    api_client.post(reverse("projects:archive", args=[created.data["id"]]))

    default_list = api_client.get(reverse("projects:list-create"))
    with_archived = api_client.get(reverse("projects:list-create"), {"include_archived": "true"})

    assert default_list.data["count"] == 0
    assert with_archived.data["count"] == 1


def test_project_list_is_paginated_and_has_no_n_plus_one(api_client, workspace_with_roles, django_assert_max_num_queries):
    workspace, owner, _admin, _member = workspace_with_roles
    _authenticate(api_client, owner)
    for i in range(6):
        api_client.post(reverse("projects:list-create"), {"workspace_id": str(workspace.id), "name": f"Project {i}"})

    with django_assert_max_num_queries(10):
        response = api_client.get(reverse("projects:list-create"))

    assert response.status_code == status.HTTP_200_OK
    assert set(response.data.keys()) == {"count", "next", "previous", "results"}
    assert response.data["count"] == 6
