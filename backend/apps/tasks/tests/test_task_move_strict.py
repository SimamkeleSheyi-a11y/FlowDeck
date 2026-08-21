import pytest
from django.urls import reverse
from rest_framework import status

from apps.boards.models import Board
from apps.tasks.models import Task
from apps.users.models import User
from apps.workspaces.models import Workspace

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
    owner = _make_user("strict_owner@example.com", "Owner")
    _authenticate(api_client, owner)
    ws = api_client.post(reverse("workspaces:list-create"), {"name": "Strict Workspace"})
    workspace = Workspace.objects.get(id=ws.data["id"])
    proj = api_client.post(reverse("projects:list-create"), {"workspace_id": str(workspace.id), "name": "Strict Project"})
    board = Board.objects.get(id=proj.data["board_id"])
    columns = list(board.columns.order_by("position"))
    return columns, owner


def test_strict_move_with_current_version_succeeds(api_client, project_with_columns):
    columns, owner = project_with_columns
    backlog, todo = columns[0], columns[1]
    _authenticate(api_client, owner)
    created = api_client.post(reverse("tasks:list-create"), {"column_id": str(backlog.id), "title": "Strict OK"})

    response = api_client.post(
        reverse("tasks:move", args=[created.data["id"]]),
        {"column_id": str(todo.id), "after_task_id": None, "version": created.data["version"], "strict": True},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data["column_id"] == str(todo.id)
    assert response.data["conflict"] is False


def test_strict_move_with_stale_version_returns_409_and_does_not_move(api_client, project_with_columns):
    columns, owner = project_with_columns
    backlog, todo = columns[0], columns[1]
    _authenticate(api_client, owner)
    created = api_client.post(reverse("tasks:list-create"), {"column_id": str(backlog.id), "title": "Strict Conflict"})
    task_id = created.data["id"]

    # someone else's edit bumps the version to 1 first
    api_client.patch(reverse("tasks:detail", args=[task_id]), {"title": "Retitled by someone else"})

    response = api_client.post(
        reverse("tasks:move", args=[task_id]),
        {"column_id": str(todo.id), "after_task_id": None, "version": 0, "strict": True},
        format="json",
    )

    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.data["code"] == "version_conflict"
    assert response.data["current"]["title"] == "Retitled by someone else"

    # the task must be completely untouched: still in backlog, same version,
    # no move applied
    task = Task.objects.get(id=task_id)
    assert task.column_id == backlog.id
    assert task.version == 1  # only the earlier patch bumped it, not this call


def test_default_behavior_unchanged_when_strict_omitted(api_client, project_with_columns):
    """Regression guard: existing Phase 5 callers that never send `strict`
    must keep getting the original accept-and-flag behavior exactly."""
    columns, owner = project_with_columns
    backlog, todo = columns[0], columns[1]
    _authenticate(api_client, owner)
    created = api_client.post(reverse("tasks:list-create"), {"column_id": str(backlog.id), "title": "No Strict Field"})
    task_id = created.data["id"]
    api_client.patch(reverse("tasks:detail", args=[task_id]), {"title": "Bumped"})

    response = api_client.post(
        reverse("tasks:move", args=[task_id]),
        {"column_id": str(todo.id), "after_task_id": None, "version": 0},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK  # not 409 — strict defaults to False
    assert response.data["conflict"] is True
    assert response.data["column_id"] == str(todo.id)  # move still applied


def test_default_behavior_unchanged_when_strict_explicitly_false(api_client, project_with_columns):
    columns, owner = project_with_columns
    backlog, todo = columns[0], columns[1]
    _authenticate(api_client, owner)
    created = api_client.post(reverse("tasks:list-create"), {"column_id": str(backlog.id), "title": "Explicit False"})
    task_id = created.data["id"]
    api_client.patch(reverse("tasks:detail", args=[task_id]), {"title": "Bumped"})

    response = api_client.post(
        reverse("tasks:move", args=[task_id]),
        {"column_id": str(todo.id), "after_task_id": None, "version": 0, "strict": False},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data["conflict"] is True
