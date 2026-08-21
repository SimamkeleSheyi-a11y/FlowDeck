import pytest
from django.urls import reverse
from rest_framework import status

from apps.boards.models import Board
from apps.projects.models import Project, ProjectMembership
from apps.tasks.models import Checklist, ChecklistItem
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
    owner = _make_user("checklist_owner@example.com", "Owner")
    _authenticate(api_client, owner)
    ws = api_client.post(reverse("workspaces:list-create"), {"name": "Checklist Workspace"})
    workspace = Workspace.objects.get(id=ws.data["id"])
    proj = api_client.post(reverse("projects:list-create"), {"workspace_id": str(workspace.id), "name": "Checklist Project"})
    board = Board.objects.get(id=proj.data["board_id"])
    column = board.columns.first()
    task = api_client.post(reverse("tasks:list-create"), {"column_id": str(column.id), "title": "Checklist task"})
    return task.data, owner


def test_get_checklist_lazily_creates_an_empty_one(api_client, project_with_task):
    task_data, owner = project_with_task
    _authenticate(api_client, owner)

    response = api_client.get(reverse("tasks:checklist", args=[task_data["id"]]))

    assert response.status_code == status.HTTP_200_OK
    assert response.data["items"] == []
    assert Checklist.objects.filter(task_id=task_data["id"]).exists()


def test_add_checklist_items_in_order(api_client, project_with_task):
    task_data, owner = project_with_task
    _authenticate(api_client, owner)

    first = api_client.post(reverse("tasks:checklist", args=[task_data["id"]]), {"text": "Registration"})
    second = api_client.post(reverse("tasks:checklist", args=[task_data["id"]]), {"text": "Login"})

    assert first.status_code == status.HTTP_201_CREATED
    assert second.status_code == status.HTTP_201_CREATED
    assert second.data["position"] > first.data["position"]

    checklist_response = api_client.get(reverse("tasks:checklist", args=[task_data["id"]]))
    texts = [item["text"] for item in checklist_response.data["items"]]
    assert texts == ["Registration", "Login"]


def test_rejects_empty_item_text(api_client, project_with_task):
    task_data, owner = project_with_task
    _authenticate(api_client, owner)

    response = api_client.post(reverse("tasks:checklist", args=[task_data["id"]]), {"text": "   "})

    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_toggle_item_done_and_edit_text(api_client, project_with_task):
    task_data, owner = project_with_task
    _authenticate(api_client, owner)
    created = api_client.post(reverse("tasks:checklist", args=[task_data["id"]]), {"text": "Password reset"})
    item_id = created.data["id"]

    response = api_client.patch(reverse("tasks:checklist-item-detail", args=[item_id]), {"is_done": True})

    assert response.status_code == status.HTTP_200_OK
    assert response.data["is_done"] is True
    assert response.data["text"] == "Password reset"


def test_delete_checklist_item(api_client, project_with_task):
    task_data, owner = project_with_task
    _authenticate(api_client, owner)
    created = api_client.post(reverse("tasks:checklist", args=[task_data["id"]]), {"text": "Temporary"})
    item_id = created.data["id"]

    response = api_client.delete(reverse("tasks:checklist-item-detail", args=[item_id]))

    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert ChecklistItem.objects.filter(id=item_id).exists() is False


def test_task_detail_reports_checklist_progress(api_client, project_with_task):
    task_data, owner = project_with_task
    _authenticate(api_client, owner)
    first = api_client.post(reverse("tasks:checklist", args=[task_data["id"]]), {"text": "Registration"})
    api_client.post(reverse("tasks:checklist", args=[task_data["id"]]), {"text": "Login"})
    api_client.patch(reverse("tasks:checklist-item-detail", args=[first.data["id"]]), {"is_done": True})

    response = api_client.get(reverse("tasks:detail", args=[task_data["id"]]))

    assert response.data["checklist_total"] == 2
    assert response.data["checklist_done"] == 1


def test_task_list_reports_checklist_progress_without_n_plus_one(
    api_client, project_with_task, django_assert_max_num_queries
):
    task_data, owner = project_with_task
    _authenticate(api_client, owner)
    first = api_client.post(reverse("tasks:checklist", args=[task_data["id"]]), {"text": "Registration"})
    api_client.patch(reverse("tasks:checklist-item-detail", args=[first.data["id"]]), {"is_done": True})

    with django_assert_max_num_queries(15):
        response = api_client.get(reverse("tasks:list-create"))

    assert response.status_code == status.HTTP_200_OK
    task_result = response.data["results"][0]
    assert task_result["checklist_total"] == 1
    assert task_result["checklist_done"] == 1


def test_non_member_cannot_see_or_edit_checklist(api_client, project_with_task):
    task_data, owner = project_with_task
    _authenticate(api_client, owner)
    created = api_client.post(reverse("tasks:checklist", args=[task_data["id"]]), {"text": "Private"})

    stranger = _make_user("checklist_stranger@example.com", "Stranger")
    _authenticate(api_client, stranger)

    get_response = api_client.get(reverse("tasks:checklist", args=[task_data["id"]]))
    patch_response = api_client.patch(reverse("tasks:checklist-item-detail", args=[created.data["id"]]), {"is_done": True})

    assert get_response.status_code == status.HTTP_404_NOT_FOUND
    assert patch_response.status_code == status.HTTP_404_NOT_FOUND


# --- checklist item reordering -------------------------------------------


def _make_three_items(api_client, task_id):
    a = api_client.post(reverse("tasks:checklist", args=[task_id]), {"text": "A"})
    b = api_client.post(reverse("tasks:checklist", args=[task_id]), {"text": "B"})
    c = api_client.post(reverse("tasks:checklist", args=[task_id]), {"text": "C"})
    return a.data, b.data, c.data


def _ordered_texts(api_client, task_id):
    response = api_client.get(reverse("tasks:checklist", args=[task_id]))
    return [item["text"] for item in response.data["items"]]


def test_reorder_item_to_first_position(api_client, project_with_task):
    task_data, owner = project_with_task
    _authenticate(api_client, owner)
    a, b, c = _make_three_items(api_client, task_data["id"])

    response = api_client.post(
        reverse("tasks:checklist-item-reorder", args=[c["id"]]), {"after_item_id": None}, format="json"
    )

    assert response.status_code == status.HTTP_200_OK
    assert _ordered_texts(api_client, task_data["id"]) == ["C", "A", "B"]


def test_reorder_item_to_middle_position(api_client, project_with_task):
    task_data, owner = project_with_task
    _authenticate(api_client, owner)
    a, b, c = _make_three_items(api_client, task_data["id"])

    response = api_client.post(
        reverse("tasks:checklist-item-reorder", args=[c["id"]]), {"after_item_id": a["id"]}
    )

    assert response.status_code == status.HTTP_200_OK
    assert _ordered_texts(api_client, task_data["id"]) == ["A", "C", "B"]


def test_reorder_item_to_last_position(api_client, project_with_task):
    task_data, owner = project_with_task
    _authenticate(api_client, owner)
    a, b, c = _make_three_items(api_client, task_data["id"])

    response = api_client.post(
        reverse("tasks:checklist-item-reorder", args=[a["id"]]), {"after_item_id": c["id"]}
    )

    assert response.status_code == status.HTTP_200_OK
    assert _ordered_texts(api_client, task_data["id"]) == ["B", "C", "A"]


def test_item_cannot_be_placed_after_itself(api_client, project_with_task):
    task_data, owner = project_with_task
    _authenticate(api_client, owner)
    a, _b, _c = _make_three_items(api_client, task_data["id"])

    response = api_client.post(
        reverse("tasks:checklist-item-reorder", args=[a["id"]]), {"after_item_id": a["id"]}
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["code"] == "invalid_position"


def test_cannot_reorder_using_after_item_from_a_different_checklist(api_client, project_with_task):
    task_data, owner = project_with_task
    _authenticate(api_client, owner)
    a, _b, _c = _make_three_items(api_client, task_data["id"])

    board = Board.objects.get(project_id=task_data["project_id"])
    other_column = board.columns.last()
    other_task = api_client.post(
        reverse("tasks:list-create"), {"column_id": str(other_column.id), "title": "Other task"}
    )
    foreign_item = api_client.post(
        reverse("tasks:checklist", args=[other_task.data["id"]]), {"text": "Foreign item"}
    )

    response = api_client.post(
        reverse("tasks:checklist-item-reorder", args=[a["id"]]), {"after_item_id": foreign_item.data["id"]}
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["code"] == "invalid_after_item"
    # nothing moved
    assert _ordered_texts(api_client, task_data["id"]) == ["A", "B", "C"]


def test_member_with_project_membership_can_reorder(api_client, project_with_task):
    task_data, owner = project_with_task
    _authenticate(api_client, owner)
    a, _b, _c = _make_three_items(api_client, task_data["id"])

    member = _make_user("checklist_reorder_member@example.com", "Member")
    project = Project.objects.get(id=task_data["project_id"])
    WorkspaceMembership.objects.create(workspace=project.workspace, user=member, role=WorkspaceRole.MEMBER)
    ProjectMembership.objects.create(project=project, user=member, added_by=owner)

    _authenticate(api_client, member)
    response = api_client.post(
        reverse("tasks:checklist-item-reorder", args=[a["id"]]), {"after_item_id": None}, format="json"
    )

    assert response.status_code == status.HTTP_200_OK


def test_non_member_cannot_reorder(api_client, project_with_task):
    task_data, owner = project_with_task
    _authenticate(api_client, owner)
    a, _b, _c = _make_three_items(api_client, task_data["id"])

    stranger = _make_user("checklist_reorder_stranger@example.com", "Stranger")
    _authenticate(api_client, stranger)

    response = api_client.post(
        reverse("tasks:checklist-item-reorder", args=[a["id"]]), {"after_item_id": None}, format="json"
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND
