import pytest
from django.urls import reverse
from rest_framework import status

from apps.boards.models import Board
from apps.tasks.models import Label, TaskLabel
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
def project_with_task(api_client):
    owner = _make_user("label_owner@example.com", "Owner")
    _authenticate(api_client, owner)
    ws = api_client.post(reverse("workspaces:list-create"), {"name": "Label Workspace"})
    workspace = Workspace.objects.get(id=ws.data["id"])
    proj = api_client.post(reverse("projects:list-create"), {"workspace_id": str(workspace.id), "name": "Label Project"})
    board = Board.objects.get(id=proj.data["board_id"])
    column = board.columns.first()
    task = api_client.post(reverse("tasks:list-create"), {"column_id": str(column.id), "title": "Labelable"})
    return proj.data, task.data, owner


def test_create_label(api_client, project_with_task):
    project_data, _task_data, owner = project_with_task
    _authenticate(api_client, owner)

    response = api_client.post(
        reverse("tasks:project-labels", args=[project_data["id"]]), {"name": "Backend", "color": "#EF4444"}
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["name"] == "Backend"
    assert response.data["color"] == "#EF4444"


def test_label_gets_default_color_when_omitted(api_client, project_with_task):
    project_data, _task_data, owner = project_with_task
    _authenticate(api_client, owner)

    response = api_client.post(reverse("tasks:project-labels", args=[project_data["id"]]), {"name": "Security"})

    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["color"] == "#6B7280"


def test_duplicate_label_name_on_same_project_rejected(api_client, project_with_task):
    project_data, _task_data, owner = project_with_task
    _authenticate(api_client, owner)
    api_client.post(reverse("tasks:project-labels", args=[project_data["id"]]), {"name": "Backend"})

    response = api_client.post(reverse("tasks:project-labels", args=[project_data["id"]]), {"name": "Backend"})

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["code"] == "duplicate_label"


def test_rename_and_delete_label(api_client, project_with_task):
    project_data, _task_data, owner = project_with_task
    _authenticate(api_client, owner)
    created = api_client.post(reverse("tasks:project-labels", args=[project_data["id"]]), {"name": "Old Name"})
    label_id = created.data["id"]

    patch_response = api_client.patch(reverse("tasks:label-detail", args=[label_id]), {"name": "New Name"})
    assert patch_response.status_code == status.HTTP_200_OK
    assert patch_response.data["name"] == "New Name"

    delete_response = api_client.delete(reverse("tasks:label-detail", args=[label_id]))
    assert delete_response.status_code == status.HTTP_204_NO_CONTENT
    assert Label.objects.filter(id=label_id).exists() is False


def test_non_member_cannot_see_project_labels(api_client, project_with_task):
    project_data, _task_data, _owner = project_with_task
    stranger = _make_user("label_stranger@example.com", "Stranger")
    _authenticate(api_client, stranger)

    response = api_client.get(reverse("tasks:project-labels", args=[project_data["id"]]))

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_attach_and_detach_label_on_task(api_client, project_with_task):
    project_data, task_data, owner = project_with_task
    _authenticate(api_client, owner)
    label = api_client.post(reverse("tasks:project-labels", args=[project_data["id"]]), {"name": "Urgent Fix"})
    label_id = label.data["id"]

    attach = api_client.post(reverse("tasks:task-labels", args=[task_data["id"]]), {"label_id": label_id})
    assert attach.status_code == status.HTTP_201_CREATED
    assert TaskLabel.objects.filter(task_id=task_data["id"], label_id=label_id).exists()

    task_detail = api_client.get(reverse("tasks:detail", args=[task_data["id"]]))
    assert [l["name"] for l in task_detail.data["labels"]] == ["Urgent Fix"]

    detach = api_client.delete(reverse("tasks:task-label-detail", args=[task_data["id"], label_id]))
    assert detach.status_code == status.HTTP_204_NO_CONTENT
    assert TaskLabel.objects.filter(task_id=task_data["id"], label_id=label_id).exists() is False


def test_attaching_the_same_label_twice_is_rejected(api_client, project_with_task):
    project_data, task_data, owner = project_with_task
    _authenticate(api_client, owner)
    label = api_client.post(reverse("tasks:project-labels", args=[project_data["id"]]), {"name": "Once Only"})
    label_id = label.data["id"]

    first = api_client.post(reverse("tasks:task-labels", args=[task_data["id"]]), {"label_id": label_id})
    second = api_client.post(reverse("tasks:task-labels", args=[task_data["id"]]), {"label_id": label_id})

    assert first.status_code == status.HTTP_201_CREATED
    assert second.status_code == status.HTTP_400_BAD_REQUEST
    assert second.data["code"] == "already_labeled"


def test_cannot_attach_a_label_from_a_different_project(api_client, project_with_task):
    project_data, task_data, owner = project_with_task
    _authenticate(api_client, owner)

    other_ws = api_client.post(reverse("workspaces:list-create"), {"name": "Other Label Workspace"})
    other_proj = api_client.post(
        reverse("projects:list-create"), {"workspace_id": other_ws.data["id"], "name": "Other Project"}
    )
    other_label = api_client.post(
        reverse("tasks:project-labels", args=[other_proj.data["id"]]), {"name": "Foreign Label"}
    )

    response = api_client.post(
        reverse("tasks:task-labels", args=[task_data["id"]]), {"label_id": other_label.data["id"]}
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND


# --- label validation corrections -----------------------------------------


def test_create_rejects_invalid_color(api_client, project_with_task):
    project_data, _task_data, owner = project_with_task
    _authenticate(api_client, owner)

    response = api_client.post(
        reverse("tasks:project-labels", args=[project_data["id"]]), {"name": "Bad Color", "color": "not-a-color"}
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_update_rejects_invalid_color(api_client, project_with_task):
    project_data, _task_data, owner = project_with_task
    _authenticate(api_client, owner)
    created = api_client.post(reverse("tasks:project-labels", args=[project_data["id"]]), {"name": "Recolor Me"})

    response = api_client.patch(reverse("tasks:label-detail", args=[created.data["id"]]), {"color": "blue"})

    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_update_accepts_a_valid_color(api_client, project_with_task):
    project_data, _task_data, owner = project_with_task
    _authenticate(api_client, owner)
    created = api_client.post(reverse("tasks:project-labels", args=[project_data["id"]]), {"name": "Recolor Me 2"})

    response = api_client.patch(reverse("tasks:label-detail", args=[created.data["id"]]), {"color": "#00FF00"})

    assert response.status_code == status.HTTP_200_OK
    assert response.data["color"] == "#00FF00"


def test_update_rejects_case_insensitive_duplicate_name(api_client, project_with_task):
    project_data, _task_data, owner = project_with_task
    _authenticate(api_client, owner)
    api_client.post(reverse("tasks:project-labels", args=[project_data["id"]]), {"name": "Backend"})
    other = api_client.post(reverse("tasks:project-labels", args=[project_data["id"]]), {"name": "Frontend"})

    response = api_client.patch(reverse("tasks:label-detail", args=[other.data["id"]]), {"name": "backend"})

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["code"] == "duplicate_label"
    # a controlled 400, never an uncaught IntegrityError/500 from the
    # unique_label_name_per_project DB constraint
    other_label = Label.objects.get(id=other.data["id"])
    assert other_label.name == "Frontend"  # untouched by the rejected rename


def test_update_excludes_the_label_itself_from_the_duplicate_check(api_client, project_with_task):
    project_data, _task_data, owner = project_with_task
    _authenticate(api_client, owner)
    created = api_client.post(reverse("tasks:project-labels", args=[project_data["id"]]), {"name": "Stable Name"})

    # re-saving with the exact same name (e.g. a color-only edit that still
    # sends "name") must not trip the duplicate check against itself
    response = api_client.patch(
        reverse("tasks:label-detail", args=[created.data["id"]]), {"name": "Stable Name", "color": "#123456"}
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data["name"] == "Stable Name"
    assert response.data["color"] == "#123456"


def test_same_label_name_allowed_in_a_different_project(api_client, project_with_task):
    project_data, _task_data, owner = project_with_task
    _authenticate(api_client, owner)
    api_client.post(reverse("tasks:project-labels", args=[project_data["id"]]), {"name": "Shared Name"})

    other_ws = api_client.post(reverse("workspaces:list-create"), {"name": "Second Label Workspace"})
    other_proj = api_client.post(
        reverse("projects:list-create"), {"workspace_id": other_ws.data["id"], "name": "Second Project"}
    )

    response = api_client.post(
        reverse("tasks:project-labels", args=[other_proj.data["id"]]), {"name": "Shared Name"}
    )

    assert response.status_code == status.HTTP_201_CREATED
