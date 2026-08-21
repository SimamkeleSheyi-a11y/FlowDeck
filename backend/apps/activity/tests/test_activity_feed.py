import pytest
from django.urls import reverse
from rest_framework import status

from apps.activity.models import ActivityEvent, ActivityEventType
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
def project_with_columns(api_client):
    owner = _make_user("activity_owner@example.com", "Owner")
    member = _make_user("activity_member@example.com", "Member")
    _authenticate(api_client, owner)
    ws = api_client.post(reverse("workspaces:list-create"), {"name": "Activity Workspace"})
    workspace = Workspace.objects.get(id=ws.data["id"])
    WorkspaceMembership.objects.create(workspace=workspace, user=member, role=WorkspaceRole.MEMBER)

    proj = api_client.post(reverse("projects:list-create"), {"workspace_id": str(workspace.id), "name": "Activity Project"})
    ProjectMembership.objects.create(project_id=proj.data["id"], user=member, added_by=owner)
    board = Board.objects.get(id=proj.data["board_id"])
    columns = list(board.columns.order_by("position"))

    return proj.data, columns, owner, member


def test_creating_a_task_logs_task_created(api_client, project_with_columns):
    _project_data, columns, owner, _member = project_with_columns
    _authenticate(api_client, owner)

    task = api_client.post(reverse("tasks:list-create"), {"column_id": str(columns[0].id), "title": "New task"})

    events = list(ActivityEvent.objects.filter(task_id=task.data["id"]))
    assert len(events) == 1
    assert events[0].event_type == ActivityEventType.TASK_CREATED
    assert events[0].actor == owner


def test_moving_a_task_logs_task_moved_with_column_names(api_client, project_with_columns):
    _project_data, columns, owner, _member = project_with_columns
    _authenticate(api_client, owner)
    task = api_client.post(reverse("tasks:list-create"), {"column_id": str(columns[0].id), "title": "Movable"})

    api_client.post(
        reverse("tasks:move", args=[task.data["id"]]),
        {"column_id": str(columns[1].id), "after_task_id": None, "version": 0},
        format="json",
    )

    event = ActivityEvent.objects.get(task_id=task.data["id"], event_type=ActivityEventType.TASK_MOVED)
    assert event.metadata["from_column"] == columns[0].name
    assert event.metadata["to_column"] == columns[1].name


def test_priority_change_logs_task_priority_changed(api_client, project_with_columns):
    _project_data, columns, owner, _member = project_with_columns
    _authenticate(api_client, owner)
    task = api_client.post(
        reverse("tasks:list-create"), {"column_id": str(columns[0].id), "title": "Prioritized", "priority": "LOW"}
    )

    api_client.patch(reverse("tasks:detail", args=[task.data["id"]]), {"priority": "HIGH"})

    event = ActivityEvent.objects.get(task_id=task.data["id"], event_type=ActivityEventType.TASK_PRIORITY_CHANGED)
    assert event.metadata == {"from": "LOW", "to": "HIGH"}


def test_completing_a_task_logs_task_completed(api_client, project_with_columns):
    _project_data, columns, owner, _member = project_with_columns
    _authenticate(api_client, owner)
    task = api_client.post(reverse("tasks:list-create"), {"column_id": str(columns[0].id), "title": "Finish me"})

    api_client.patch(reverse("tasks:detail", args=[task.data["id"]]), {"is_completed": True})

    assert ActivityEvent.objects.filter(
        task_id=task.data["id"], event_type=ActivityEventType.TASK_COMPLETED
    ).exists()


def test_assigning_a_task_logs_task_assigned(api_client, project_with_columns):
    _project_data, columns, owner, member = project_with_columns
    _authenticate(api_client, owner)
    task = api_client.post(reverse("tasks:list-create"), {"column_id": str(columns[0].id), "title": "Assign target"})

    api_client.post(reverse("tasks:assignees", args=[task.data["id"]]), {"user_id": str(member.id)})

    event = ActivityEvent.objects.get(task_id=task.data["id"], event_type=ActivityEventType.TASK_ASSIGNED)
    assert str(event.target_id) == str(member.id)


def test_adding_a_comment_logs_comment_added(api_client, project_with_columns):
    _project_data, columns, owner, _member = project_with_columns
    _authenticate(api_client, owner)
    task = api_client.post(reverse("tasks:list-create"), {"column_id": str(columns[0].id), "title": "Discuss me"})

    api_client.post(reverse("comments:task-comments", args=[task.data["id"]]), {"body": "Login endpoint is working."})

    assert ActivityEvent.objects.filter(
        task_id=task.data["id"], event_type=ActivityEventType.COMMENT_ADDED
    ).exists()


def test_activity_feed_is_paginated_and_newest_first(api_client, project_with_columns):
    _project_data, columns, owner, _member = project_with_columns
    _authenticate(api_client, owner)
    task = api_client.post(reverse("tasks:list-create"), {"column_id": str(columns[0].id), "title": "Feed task"})
    api_client.patch(reverse("tasks:detail", args=[task.data["id"]]), {"priority": "URGENT"})

    response = api_client.get(reverse("activity:task-activity", args=[task.data["id"]]))

    assert response.status_code == status.HTTP_200_OK
    assert set(response.data.keys()) == {"count", "next", "previous", "results"}
    assert response.data["count"] == 2  # TASK_CREATED, then TASK_PRIORITY_CHANGED
    event_types = [e["event_type"] for e in response.data["results"]]
    assert event_types[0] == ActivityEventType.TASK_PRIORITY_CHANGED  # newest first
    assert event_types[1] == ActivityEventType.TASK_CREATED


def test_activity_feed_denied_for_non_member(api_client, project_with_columns):
    _project_data, columns, owner, _member = project_with_columns
    _authenticate(api_client, owner)
    task = api_client.post(reverse("tasks:list-create"), {"column_id": str(columns[0].id), "title": "Private task"})

    stranger = _make_user("activity_stranger@example.com", "Stranger")
    _authenticate(api_client, stranger)
    response = api_client.get(reverse("activity:task-activity", args=[task.data["id"]]))

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_activity_feed_visible_to_project_member(api_client, project_with_columns):
    _project_data, columns, owner, member = project_with_columns
    _authenticate(api_client, owner)
    task = api_client.post(reverse("tasks:list-create"), {"column_id": str(columns[0].id), "title": "Shared task"})

    _authenticate(api_client, member)
    response = api_client.get(reverse("activity:task-activity", args=[task.data["id"]]))

    assert response.status_code == status.HTTP_200_OK
    assert response.data["count"] == 1
