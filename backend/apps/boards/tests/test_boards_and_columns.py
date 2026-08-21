import pytest
from django.urls import reverse
from rest_framework import status

from apps.boards.models import Board, BoardColumn
from apps.projects.models import ProjectMembership
from apps.users.models import User
from apps.workspaces.models import Workspace, WorkspaceMembership, WorkspaceRole

pytestmark = pytest.mark.django_db

PASSWORD = "TestPass123!"
DEFAULT_COLUMNS = ["Backlog", "To Do", "In Progress", "Review", "Done"]


def _make_user(email, display_name, verified=True):
    user = User.objects.create_user(email=email, password=PASSWORD, display_name=display_name)
    if verified:
        user.is_email_verified = True
        user.save(update_fields=["is_email_verified"])
    return user


def _authenticate(api_client, user):
    api_client.force_authenticate(user=user)


@pytest.fixture
def workspace_with_project(api_client):
    owner = _make_user("board_owner@example.com", "Owner")
    admin = _make_user("board_admin@example.com", "Admin")
    member = _make_user("board_member@example.com", "Member")
    _authenticate(api_client, owner)
    ws = api_client.post(reverse("workspaces:list-create"), {"name": "Board Workspace"})
    workspace = Workspace.objects.get(id=ws.data["id"])
    WorkspaceMembership.objects.create(workspace=workspace, user=admin, role=WorkspaceRole.ADMIN)
    WorkspaceMembership.objects.create(workspace=workspace, user=member, role=WorkspaceRole.MEMBER)

    proj = api_client.post(reverse("projects:list-create"), {"workspace_id": str(workspace.id), "name": "Board Project"})
    return workspace, proj.data, owner, admin, member


def test_project_creation_auto_creates_board_with_default_columns(api_client, workspace_with_project):
    _workspace, project_data, _owner, _admin, _member = workspace_with_project

    assert project_data["board_id"] is not None
    board = Board.objects.get(id=project_data["board_id"])
    names = list(board.columns.order_by("position").values_list("name", flat=True))
    assert names == DEFAULT_COLUMNS


def test_board_detail_returns_nested_columns_in_order(api_client, workspace_with_project):
    _workspace, project_data, owner, _admin, _member = workspace_with_project
    _authenticate(api_client, owner)

    response = api_client.get(reverse("boards:detail", args=[project_data["board_id"]]))

    assert response.status_code == status.HTTP_200_OK
    assert [c["name"] for c in response.data["columns"]] == DEFAULT_COLUMNS


def test_member_without_project_access_gets_404_for_board(api_client, workspace_with_project):
    _workspace, project_data, _owner, _admin, _member = workspace_with_project
    stranger = _make_user("board_stranger@example.com", "Stranger")
    _authenticate(api_client, stranger)

    response = api_client.get(reverse("boards:detail", args=[project_data["board_id"]]))

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_admin_can_create_a_column(api_client, workspace_with_project):
    _workspace, project_data, _owner, admin, _member = workspace_with_project
    _authenticate(api_client, admin)

    response = api_client.post(
        reverse("boards:columns", args=[project_data["board_id"]]), {"name": "Blocked"}
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["name"] == "Blocked"
    # appended after the 5 defaults
    assert response.data["position"] > 5000


def test_member_cannot_create_a_column(api_client, workspace_with_project):
    _workspace, project_data, owner, _admin, member = workspace_with_project
    # This test is about role permission (a project MEMBER can't manage
    # board structure), not project visibility — give the member explicit
    # ProjectMembership first so they can see the project at all, isolating
    # the thing actually under test. Without this, the correct response is
    # 404 (can't discover the project), not 403 — a different, already
    # separately-tested behavior (test_member_without_project_access_gets_404_for_board).
    ProjectMembership.objects.create(project_id=project_data["id"], user=member, added_by=owner)
    _authenticate(api_client, member)

    response = api_client.post(
        reverse("boards:columns", args=[project_data["board_id"]]), {"name": "Should Fail"}
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_admin_can_rename_a_column(api_client, workspace_with_project):
    _workspace, project_data, _owner, admin, _member = workspace_with_project
    board = Board.objects.get(id=project_data["board_id"])
    column = board.columns.first()
    _authenticate(api_client, admin)

    response = api_client.patch(reverse("boards:column-detail", args=[column.id]), {"name": "Renamed"})

    assert response.status_code == status.HTTP_200_OK
    assert response.data["name"] == "Renamed"


def test_deleting_a_non_empty_column_is_rejected(api_client, workspace_with_project):
    _workspace, project_data, owner, admin, _member = workspace_with_project
    board = Board.objects.get(id=project_data["board_id"])
    column = board.columns.first()
    _authenticate(api_client, owner)
    api_client.post(
        reverse("tasks:list-create"), {"column_id": str(column.id), "title": "Blocking task"}
    )

    _authenticate(api_client, admin)
    response = api_client.delete(reverse("boards:column-detail", args=[column.id]))

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["code"] == "column_not_empty"
    assert BoardColumn.objects.filter(id=column.id).exists()


def test_deleting_an_empty_column_succeeds(api_client, workspace_with_project):
    _workspace, project_data, _owner, admin, _member = workspace_with_project
    board = Board.objects.get(id=project_data["board_id"])
    column = board.columns.last()  # "Done" — empty by default
    _authenticate(api_client, admin)

    response = api_client.delete(reverse("boards:column-detail", args=[column.id]))

    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert BoardColumn.objects.filter(id=column.id).exists() is False


def test_reorder_column_to_first_position(api_client, workspace_with_project):
    _workspace, project_data, _owner, admin, _member = workspace_with_project
    board = Board.objects.get(id=project_data["board_id"])
    done_column = board.columns.order_by("position").last()  # "Done"
    _authenticate(api_client, admin)

    response = api_client.post(
        reverse("boards:column-reorder", args=[done_column.id]), {"after_column_id": None}, format="json"
    )

    assert response.status_code == status.HTTP_200_OK
    board.refresh_from_db()
    ordered_names = list(board.columns.order_by("position").values_list("name", flat=True))
    assert ordered_names[0] == "Done"


def test_reorder_column_between_two_others(api_client, workspace_with_project):
    _workspace, project_data, _owner, admin, _member = workspace_with_project
    board = Board.objects.get(id=project_data["board_id"])
    columns = list(board.columns.order_by("position"))
    backlog, todo, in_progress, review, done = columns
    _authenticate(api_client, admin)

    # move "Done" to sit between "To Do" and "In Progress"
    response = api_client.post(reverse("boards:column-reorder", args=[done.id]), {"after_column_id": str(todo.id)})

    assert response.status_code == status.HTTP_200_OK
    ordered_names = list(board.columns.order_by("position").values_list("name", flat=True))
    assert ordered_names == ["Backlog", "To Do", "Done", "In Progress", "Review"]


def test_column_cannot_be_placed_after_itself(api_client, workspace_with_project):
    _workspace, project_data, _owner, admin, _member = workspace_with_project
    board = Board.objects.get(id=project_data["board_id"])
    column = board.columns.first()
    _authenticate(api_client, admin)

    response = api_client.post(
        reverse("boards:column-reorder", args=[column.id]), {"after_column_id": str(column.id)}
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
