import pytest
from django.urls import reverse
from rest_framework import status

from apps.boards.models import Board
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
    owner = _make_user("move_owner@example.com", "Owner")
    _authenticate(api_client, owner)
    ws = api_client.post(reverse("workspaces:list-create"), {"name": "Move Workspace"})
    workspace = Workspace.objects.get(id=ws.data["id"])
    proj = api_client.post(
        reverse("projects:list-create"), {"workspace_id": str(workspace.id), "name": "Move Project"}
    )
    board = Board.objects.get(id=proj.data["board_id"])
    columns = list(board.columns.order_by("position"))
    return proj.data, columns, owner


def _create_task(api_client, column_id, title):
    return api_client.post(reverse("tasks:list-create"), {"column_id": column_id, "title": title})


def test_move_task_to_a_different_column(api_client, project_with_columns):
    _project_data, columns, owner = project_with_columns
    backlog, todo = columns[0], columns[1]
    _authenticate(api_client, owner)
    created = _create_task(api_client, str(backlog.id), "Movable task")
    task_id = created.data["id"]

    response = api_client.post(
        reverse("tasks:move", args=[task_id]),
        {"column_id": str(todo.id), "after_task_id": None, "version": 0},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data["column_id"] == str(todo.id)
    assert response.data["conflict"] is False
    assert response.data["version"] == 1


def test_move_task_between_two_siblings_computes_midpoint(api_client, project_with_columns):
    _project_data, columns, owner = project_with_columns
    backlog = columns[0]
    _authenticate(api_client, owner)
    first = _create_task(api_client, str(backlog.id), "First")
    second = _create_task(api_client, str(backlog.id), "Second")
    third = _create_task(api_client, str(backlog.id), "Third")

    # move "Third" to sit between "First" and "Second"
    response = api_client.post(
        reverse("tasks:move", args=[third.data["id"]]),
        {"column_id": str(backlog.id), "after_task_id": first.data["id"], "version": 0},
    )

    assert response.status_code == status.HTTP_200_OK
    ordered_titles = list(
        backlog.tasks.order_by("position").values_list("title", flat=True)
    )
    assert ordered_titles == ["First", "Third", "Second"]


def test_move_with_stale_version_still_applies_but_flags_conflict(api_client, project_with_columns):
    _project_data, columns, owner = project_with_columns
    backlog, todo = columns[0], columns[1]
    _authenticate(api_client, owner)
    created = _create_task(api_client, str(backlog.id), "Contested task")
    task_id = created.data["id"]

    # someone else's edit bumps the version to 1 first
    api_client.patch(reverse("tasks:detail", args=[task_id]), {"title": "Retitled by someone else"})

    # this move submits the stale version=0 it originally loaded
    response = api_client.post(
        reverse("tasks:move", args=[task_id]),
        {"column_id": str(todo.id), "after_task_id": None, "version": 0},
        format="json",
    )

    # Phase 5/8 MVP: last-write-wins, but the conflict is surfaced, not hidden
    assert response.status_code == status.HTTP_200_OK
    assert response.data["conflict"] is True
    assert response.data["column_id"] == str(todo.id)  # the move still applied
    assert response.data["version"] == 2  # 0 -> 1 (patch) -> 2 (move)


def test_move_with_current_version_reports_no_conflict(api_client, project_with_columns):
    _project_data, columns, owner = project_with_columns
    backlog, todo = columns[0], columns[1]
    _authenticate(api_client, owner)
    created = _create_task(api_client, str(backlog.id), "Uncontested task")
    task_id = created.data["id"]

    response = api_client.post(
        reverse("tasks:move", args=[task_id]),
        {"column_id": str(todo.id), "after_task_id": None, "version": created.data["version"]},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data["conflict"] is False


def test_cannot_move_task_to_a_column_on_another_project(api_client, project_with_columns):
    project_data, columns, owner = project_with_columns
    _authenticate(api_client, owner)
    created = _create_task(api_client, str(columns[0].id), "Cross-project attempt")

    other_ws = api_client.post(reverse("workspaces:list-create"), {"name": "Other Workspace"})
    other_proj = api_client.post(
        reverse("projects:list-create"), {"workspace_id": other_ws.data["id"], "name": "Other Project"}
    )
    other_board = Board.objects.get(id=other_proj.data["board_id"])
    other_column = other_board.columns.first()

    response = api_client.post(
        reverse("tasks:move", args=[created.data["id"]]),
        {"column_id": str(other_column.id), "after_task_id": None, "version": 0},
        format="json",
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_task_cannot_be_placed_after_itself(api_client, project_with_columns):
    _project_data, columns, owner = project_with_columns
    _authenticate(api_client, owner)
    created = _create_task(api_client, str(columns[0].id), "Self-referential")

    response = api_client.post(
        reverse("tasks:move", args=[created.data["id"]]),
        {"column_id": str(columns[0].id), "after_task_id": created.data["id"], "version": 0},
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
