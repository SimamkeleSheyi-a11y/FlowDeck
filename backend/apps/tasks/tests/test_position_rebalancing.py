import pytest
from django.urls import reverse
from rest_framework import status

from apps.boards.models import Board
from apps.tasks.models import ChecklistItem, Task
from apps.tasks.services import MIN_GAP
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
def project_owner(api_client):
    owner = _make_user("task_rebalance_owner@example.com", "Owner")
    _authenticate(api_client, owner)
    ws = api_client.post(reverse("workspaces:list-create"), {"name": "Task Rebalance Workspace"})
    workspace = Workspace.objects.get(id=ws.data["id"])
    proj = api_client.post(
        reverse("projects:list-create"), {"workspace_id": str(workspace.id), "name": "Task Rebalance Project"}
    )
    board = Board.objects.get(id=proj.data["board_id"])
    column = board.columns.first()
    return column, owner


# --- tasks within a column ---------------------------------------------


def test_task_rebalance_triggers_when_gap_too_small(api_client, project_owner):
    column, owner = project_owner
    _authenticate(api_client, owner)
    anchor = api_client.post(reverse("tasks:list-create"), {"column_id": str(column.id), "title": "Anchor"})
    anchor_task = Task.objects.get(id=anchor.data["id"])

    # Simulate the end-state of many prior narrowing moves directly.
    Task.objects.create(
        column=column,
        project_id=anchor_task.project_id,
        title="Tight",
        position=anchor_task.position + MIN_GAP / 10,
        created_by=owner,
    )

    new_task = api_client.post(reverse("tasks:list-create"), {"column_id": str(column.id), "title": "Inserted"})
    response = api_client.post(
        reverse("tasks:move", args=[new_task.data["id"]]),
        {"column_id": str(column.id), "after_task_id": str(anchor_task.id), "version": 0},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    positions = list(column.tasks.order_by("position").values_list("position", flat=True))
    assert len(positions) == len(set(positions))
    gaps = [b - a for a, b in zip(positions, positions[1:])]
    assert all(gap >= MIN_GAP * 1000 for gap in gaps)


def test_repeated_task_moves_never_produce_duplicate_or_unstable_positions(api_client, project_owner):
    column, owner = project_owner
    _authenticate(api_client, owner)
    anchor = api_client.post(reverse("tasks:list-create"), {"column_id": str(column.id), "title": "Anchor"})

    for i in range(40):
        created = api_client.post(reverse("tasks:list-create"), {"column_id": str(column.id), "title": f"Loop {i}"})
        response = api_client.post(
            reverse("tasks:move", args=[created.data["id"]]),
            {"column_id": str(column.id), "after_task_id": anchor.data["id"], "version": 0},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK, f"iteration {i} failed: {response.data}"

    positions = list(column.tasks.order_by("position").values_list("position", flat=True))
    assert len(positions) == len(set(positions))
    assert positions == sorted(positions)


# --- checklist items within a checklist ---------------------------------


def test_checklist_item_rebalance_triggers_when_gap_too_small(api_client, project_owner):
    column, owner = project_owner
    _authenticate(api_client, owner)
    task = api_client.post(reverse("tasks:list-create"), {"column_id": str(column.id), "title": "Checklist host"})
    anchor = api_client.post(reverse("tasks:checklist", args=[task.data["id"]]), {"text": "Anchor item"})
    anchor_item = ChecklistItem.objects.get(id=anchor.data["id"])

    ChecklistItem.objects.create(
        checklist_id=anchor_item.checklist_id, text="Tight", position=anchor_item.position + MIN_GAP / 10
    )

    new_item = api_client.post(reverse("tasks:checklist", args=[task.data["id"]]), {"text": "Inserted"})
    response = api_client.post(
        reverse("tasks:checklist-item-reorder", args=[new_item.data["id"]]),
        {"after_item_id": anchor_item.id},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    positions = list(
        ChecklistItem.objects.filter(checklist_id=anchor_item.checklist_id).order_by("position").values_list(
            "position", flat=True
        )
    )
    assert len(positions) == len(set(positions))
    gaps = [b - a for a, b in zip(positions, positions[1:])]
    assert all(gap >= MIN_GAP * 1000 for gap in gaps)


def test_repeated_checklist_item_reorders_never_produce_duplicate_positions(api_client, project_owner):
    column, owner = project_owner
    _authenticate(api_client, owner)
    task = api_client.post(reverse("tasks:list-create"), {"column_id": str(column.id), "title": "Checklist host 2"})
    anchor = api_client.post(reverse("tasks:checklist", args=[task.data["id"]]), {"text": "Anchor"})

    for i in range(40):
        created = api_client.post(reverse("tasks:checklist", args=[task.data["id"]]), {"text": f"Loop {i}"})
        response = api_client.post(
            reverse("tasks:checklist-item-reorder", args=[created.data["id"]]),
            {"after_item_id": anchor.data["id"]},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK, f"iteration {i} failed: {response.data}"

    checklist_id = ChecklistItem.objects.get(id=anchor.data["id"]).checklist_id
    positions = list(
        ChecklistItem.objects.filter(checklist_id=checklist_id).order_by("position").values_list("position", flat=True)
    )
    assert len(positions) == len(set(positions))
    assert positions == sorted(positions)
