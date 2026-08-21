import pytest
from django.urls import reverse
from rest_framework import status

from apps.boards.models import Board
from apps.tasks.models import Task
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
def project_with_columns(api_client):
    owner = _make_user("task_owner@example.com", "Owner")
    member = _make_user("task_member@example.com", "Member")
    _authenticate(api_client, owner)
    ws = api_client.post(reverse("workspaces:list-create"), {"name": "Task Workspace"})
    workspace = Workspace.objects.get(id=ws.data["id"])
    WorkspaceMembership.objects.create(workspace=workspace, user=member, role=WorkspaceRole.MEMBER)

    from apps.projects.models import ProjectMembership

    proj = api_client.post(reverse("projects:list-create"), {"workspace_id": str(workspace.id), "name": "Task Project"})
    board = Board.objects.get(id=proj.data["board_id"])
    ProjectMembership.objects.create(project_id=proj.data["id"], user=member, added_by=owner)
    columns = list(board.columns.order_by("position"))
    return proj.data, columns, owner, member


def test_project_member_can_create_task(api_client, project_with_columns):
    project_data, columns, _owner, member = project_with_columns
    todo = columns[1]
    _authenticate(api_client, member)

    response = api_client.post(
        reverse("tasks:list-create"),
        {"column_id": str(todo.id), "title": "Build login page", "priority": "HIGH"},
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["title"] == "Build login page"
    assert response.data["priority"] == "HIGH"
    assert response.data["column_id"] == str(todo.id)
    assert response.data["project_id"] == project_data["id"]
    assert response.data["version"] == 0
    assert response.data["is_completed"] is False


def test_non_member_cannot_create_task(api_client, project_with_columns):
    _project_data, columns, _owner, _member = project_with_columns
    stranger = _make_user("task_stranger@example.com", "Stranger")
    _authenticate(api_client, stranger)

    response = api_client.post(
        reverse("tasks:list-create"), {"column_id": str(columns[0].id), "title": "Sneaky Task"}
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert Task.objects.filter(title="Sneaky Task").exists() is False


def test_task_rejects_due_date_before_start_date(api_client, project_with_columns):
    _project_data, columns, owner, _member = project_with_columns
    _authenticate(api_client, owner)

    response = api_client.post(
        reverse("tasks:list-create"),
        {
            "column_id": str(columns[0].id),
            "title": "Bad dates",
            "start_date": "2026-08-10",
            "due_date": "2026-08-01",
        },
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_get_and_patch_task(api_client, project_with_columns):
    _project_data, columns, owner, _member = project_with_columns
    _authenticate(api_client, owner)
    created = api_client.post(
        reverse("tasks:list-create"), {"column_id": str(columns[0].id), "title": "Original title"}
    )
    task_id = created.data["id"]

    get_response = api_client.get(reverse("tasks:detail", args=[task_id]))
    assert get_response.status_code == status.HTTP_200_OK
    assert get_response.data["title"] == "Original title"

    patch_response = api_client.patch(
        reverse("tasks:detail", args=[task_id]), {"title": "Updated title", "is_completed": True}
    )
    assert patch_response.status_code == status.HTTP_200_OK
    assert patch_response.data["title"] == "Updated title"
    assert patch_response.data["is_completed"] is True
    assert patch_response.data["version"] == 1  # bumped by the edit


def test_delete_task(api_client, project_with_columns):
    _project_data, columns, owner, _member = project_with_columns
    _authenticate(api_client, owner)
    created = api_client.post(reverse("tasks:list-create"), {"column_id": str(columns[0].id), "title": "Doomed"})

    response = api_client.delete(reverse("tasks:detail", args=[created.data["id"]]))

    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert Task.objects.filter(id=created.data["id"]).exists() is False


def test_non_member_gets_404_for_task_detail(api_client, project_with_columns):
    _project_data, columns, owner, _member = project_with_columns
    _authenticate(api_client, owner)
    created = api_client.post(reverse("tasks:list-create"), {"column_id": str(columns[0].id), "title": "Hidden"})

    stranger = _make_user("task_detail_stranger@example.com", "Stranger")
    _authenticate(api_client, stranger)
    response = api_client.get(reverse("tasks:detail", args=[created.data["id"]]))

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_task_list_is_paginated_and_filterable_by_column(api_client, project_with_columns):
    _project_data, columns, owner, _member = project_with_columns
    _authenticate(api_client, owner)
    for i in range(3):
        api_client.post(reverse("tasks:list-create"), {"column_id": str(columns[0].id), "title": f"Task {i}"})
    api_client.post(reverse("tasks:list-create"), {"column_id": str(columns[1].id), "title": "Other column task"})

    response = api_client.get(reverse("tasks:list-create"), {"column": str(columns[0].id)})

    assert response.status_code == status.HTTP_200_OK
    assert set(response.data.keys()) == {"count", "next", "previous", "results"}
    assert response.data["count"] == 3
