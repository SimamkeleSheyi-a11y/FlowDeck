import pytest
from django.urls import reverse
from rest_framework import status

from apps.boards.models import Board
from apps.projects.models import ProjectMembership
from apps.tasks.models import TaskAssignee
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
    api_client.force_authenticate(user=user)


@pytest.fixture
def project_with_task(api_client):
    owner = _make_user("assignee_owner@example.com", "Owner")
    teammate = _make_user("assignee_teammate@example.com", "Teammate")
    outsider = _make_user("assignee_outsider@example.com", "Outsider")
    _authenticate(api_client, owner)
    ws = api_client.post(reverse("workspaces:list-create"), {"name": "Assignee Workspace"})
    workspace = Workspace.objects.get(id=ws.data["id"])
    WorkspaceMembership.objects.create(workspace=workspace, user=teammate, role=WorkspaceRole.MEMBER)

    proj = api_client.post(reverse("projects:list-create"), {"workspace_id": str(workspace.id), "name": "Assignee Project"})
    ProjectMembership.objects.create(project_id=proj.data["id"], user=teammate, added_by=owner)
    board = Board.objects.get(id=proj.data["board_id"])
    column = board.columns.first()
    task = api_client.post(reverse("tasks:list-create"), {"column_id": str(column.id), "title": "Assign me"})

    return task.data, owner, teammate, outsider


def test_can_assign_a_project_member(api_client, project_with_task):
    task_data, owner, teammate, _outsider = project_with_task
    _authenticate(api_client, owner)

    response = api_client.post(reverse("tasks:assignees", args=[task_data["id"]]), {"user_id": str(teammate.id)})

    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["user"]["email"] == teammate.email
    assert TaskAssignee.objects.filter(task_id=task_data["id"], user=teammate).exists()


def test_cannot_assign_someone_outside_the_project(api_client, project_with_task):
    task_data, owner, _teammate, outsider = project_with_task
    _authenticate(api_client, owner)

    response = api_client.post(reverse("tasks:assignees", args=[task_data["id"]]), {"user_id": str(outsider.id)})

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["code"] == "not_project_member"


def test_assigning_the_same_user_twice_is_rejected(api_client, project_with_task):
    task_data, owner, teammate, _outsider = project_with_task
    _authenticate(api_client, owner)

    first = api_client.post(reverse("tasks:assignees", args=[task_data["id"]]), {"user_id": str(teammate.id)})
    second = api_client.post(reverse("tasks:assignees", args=[task_data["id"]]), {"user_id": str(teammate.id)})

    assert first.status_code == status.HTTP_201_CREATED
    assert second.status_code == status.HTTP_400_BAD_REQUEST
    assert second.data["code"] == "already_assigned"
    assert TaskAssignee.objects.filter(task_id=task_data["id"], user=teammate).count() == 1


def test_can_unassign(api_client, project_with_task):
    task_data, owner, teammate, _outsider = project_with_task
    _authenticate(api_client, owner)
    api_client.post(reverse("tasks:assignees", args=[task_data["id"]]), {"user_id": str(teammate.id)})

    response = api_client.delete(reverse("tasks:assignee-detail", args=[task_data["id"], teammate.id]))

    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert TaskAssignee.objects.filter(task_id=task_data["id"], user=teammate).exists() is False


def test_task_detail_reflects_assignees(api_client, project_with_task):
    task_data, owner, teammate, _outsider = project_with_task
    _authenticate(api_client, owner)
    api_client.post(reverse("tasks:assignees", args=[task_data["id"]]), {"user_id": str(teammate.id)})

    response = api_client.get(reverse("tasks:detail", args=[task_data["id"]]))

    assert response.status_code == status.HTTP_200_OK
    assert len(response.data["assignees"]) == 1
    assert response.data["assignees"][0]["user"]["email"] == teammate.email


def test_non_member_cannot_assign(api_client, project_with_task):
    task_data, _owner, teammate, outsider = project_with_task
    _authenticate(api_client, outsider)

    response = api_client.post(reverse("tasks:assignees", args=[task_data["id"]]), {"user_id": str(teammate.id)})

    assert response.status_code == status.HTTP_404_NOT_FOUND
