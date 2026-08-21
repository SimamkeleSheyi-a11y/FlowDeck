import pytest
from django.urls import reverse
from rest_framework import status

from apps.boards.models import Board
from apps.projects.models import ProjectMembership
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
def project_with_tasks(api_client):
    owner = _make_user("full_owner@example.com", "Owner")
    member = _make_user("full_member@example.com", "Member")
    _authenticate(api_client, owner)
    ws = api_client.post(reverse("workspaces:list-create"), {"name": "Full Board Workspace"})
    workspace = Workspace.objects.get(id=ws.data["id"])
    WorkspaceMembership.objects.create(workspace=workspace, user=member, role=WorkspaceRole.MEMBER)

    proj = api_client.post(reverse("projects:list-create"), {"workspace_id": str(workspace.id), "name": "Full Board Project"})
    ProjectMembership.objects.create(project_id=proj.data["id"], user=member, added_by=owner)
    board = Board.objects.get(id=proj.data["board_id"])
    columns = list(board.columns.order_by("position"))

    backlog, todo = columns[0], columns[1]
    task_a = api_client.post(reverse("tasks:list-create"), {"column_id": str(backlog.id), "title": "Task A", "priority": "HIGH"})
    task_b = api_client.post(reverse("tasks:list-create"), {"column_id": str(backlog.id), "title": "Task B"})
    api_client.post(reverse("tasks:assignees", args=[task_a.data["id"]]), {"user_id": str(member.id)})
    label = api_client.post(reverse("tasks:project-labels", args=[proj.data["id"]]), {"name": "Backend"})
    api_client.post(reverse("tasks:task-labels", args=[task_a.data["id"]]), {"label_id": label.data["id"]})
    item = api_client.post(reverse("tasks:checklist", args=[task_a.data["id"]]), {"text": "Step one"})
    api_client.patch(reverse("tasks:checklist-item-detail", args=[item.data["id"]]), {"is_done": True})

    return proj.data, board, columns, owner, member, task_a.data, task_b.data


def test_full_board_nests_tasks_in_position_order_within_each_column(api_client, project_with_tasks):
    _project_data, board, _columns, owner, _member, task_a, task_b = project_with_tasks
    _authenticate(api_client, owner)

    response = api_client.get(reverse("boards:full", args=[board.id]))

    assert response.status_code == status.HTTP_200_OK
    column_names = [c["name"] for c in response.data["columns"]]
    assert column_names == ["Backlog", "To Do", "In Progress", "Review", "Done"]

    backlog_column = response.data["columns"][0]
    task_titles = [t["title"] for t in backlog_column["tasks"]]
    assert task_titles == ["Task A", "Task B"]


def test_full_board_task_includes_assignees_labels_checklist_priority_dates_version(api_client, project_with_tasks):
    _project_data, board, _columns, owner, member, task_a, _task_b = project_with_tasks
    _authenticate(api_client, owner)

    response = api_client.get(reverse("boards:full", args=[board.id]))

    task_data = response.data["columns"][0]["tasks"][0]
    assert task_data["id"] == task_a["id"]
    assert task_data["priority"] == "HIGH"
    assert task_data["assignees"][0]["user"]["email"] == member.email
    assert task_data["labels"][0]["name"] == "Backend"
    assert task_data["checklist_total"] == 1
    assert task_data["checklist_done"] == 1
    assert "due_date" in task_data
    assert "start_date" in task_data
    assert task_data["version"] == 0


def test_existing_board_detail_endpoint_unchanged_by_full_endpoint(api_client, project_with_tasks):
    _project_data, board, _columns, owner, _member, _task_a, _task_b = project_with_tasks
    _authenticate(api_client, owner)

    response = api_client.get(reverse("boards:detail", args=[board.id]))

    assert response.status_code == status.HTTP_200_OK
    # unchanged shape: columns present, but no nested "tasks" key at all
    assert "tasks" not in response.data["columns"][0]


def test_full_board_denied_for_non_member(api_client, project_with_tasks):
    _project_data, board, _columns, _owner, _member, _task_a, _task_b = project_with_tasks
    stranger = _make_user("full_stranger@example.com", "Stranger")
    _authenticate(api_client, stranger)

    response = api_client.get(reverse("boards:full", args=[board.id]))

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_full_board_visible_to_project_member(api_client, project_with_tasks):
    _project_data, board, _columns, _owner, member, _task_a, _task_b = project_with_tasks
    _authenticate(api_client, member)

    response = api_client.get(reverse("boards:full", args=[board.id]))

    assert response.status_code == status.HTTP_200_OK


def test_full_board_is_n_plus_one_safe(api_client, project_with_tasks, django_assert_max_num_queries):
    _project_data, board, columns, owner, _member, _task_a, _task_b = project_with_tasks
    _authenticate(api_client, owner)
    # pile on more tasks across columns — the query count for the full
    # board fetch must not grow with how many tasks/columns exist
    for i in range(10):
        api_client.post(
            reverse("tasks:list-create"), {"column_id": str(columns[i % len(columns)].id), "title": f"Bulk {i}"}
        )

    with django_assert_max_num_queries(20):
        response = api_client.get(reverse("boards:full", args=[board.id]))

    assert response.status_code == status.HTTP_200_OK
    total_tasks = sum(len(c["tasks"]) for c in response.data["columns"])
    assert total_tasks == 12  # 2 from the fixture + 10 bulk
