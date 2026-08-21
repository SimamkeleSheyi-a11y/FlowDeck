import pytest
from django.urls import reverse
from rest_framework import status

from apps.boards.models import Board
from apps.comments.models import Comment
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
def project_with_task(api_client):
    owner = _make_user("comment_owner@example.com", "Owner")
    member = _make_user("comment_member@example.com", "Member")
    _authenticate(api_client, owner)
    ws = api_client.post(reverse("workspaces:list-create"), {"name": "Comment Workspace"})
    workspace = Workspace.objects.get(id=ws.data["id"])
    WorkspaceMembership.objects.create(workspace=workspace, user=member, role=WorkspaceRole.MEMBER)

    proj = api_client.post(reverse("projects:list-create"), {"workspace_id": str(workspace.id), "name": "Comment Project"})
    ProjectMembership.objects.create(project_id=proj.data["id"], user=member, added_by=owner)
    board = Board.objects.get(id=proj.data["board_id"])
    column = board.columns.first()
    task = api_client.post(reverse("tasks:list-create"), {"column_id": str(column.id), "title": "Commentable task"})

    return task.data, owner, member


def test_project_member_can_add_comment(api_client, project_with_task):
    task_data, owner, _member = project_with_task
    _authenticate(api_client, owner)

    response = api_client.post(reverse("comments:task-comments", args=[task_data["id"]]), {"body": "Login endpoint is working."})

    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["body"] == "Login endpoint is working."
    assert response.data["author"]["email"] == owner.email
    assert response.data["edited_at"] is None


def test_non_member_cannot_comment(api_client, project_with_task):
    task_data, _owner, _member = project_with_task
    stranger = _make_user("comment_stranger@example.com", "Stranger")
    _authenticate(api_client, stranger)

    response = api_client.post(reverse("comments:task-comments", args=[task_data["id"]]), {"body": "Sneaky"})

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert Comment.objects.filter(body="Sneaky").exists() is False


def test_rejects_empty_comment(api_client, project_with_task):
    task_data, owner, _member = project_with_task
    _authenticate(api_client, owner)

    response = api_client.post(reverse("comments:task-comments", args=[task_data["id"]]), {"body": "   "})

    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_comments_listed_in_chronological_order(api_client, project_with_task):
    task_data, owner, member = project_with_task
    _authenticate(api_client, owner)
    api_client.post(reverse("comments:task-comments", args=[task_data["id"]]), {"body": "First"})
    _authenticate(api_client, member)
    api_client.post(reverse("comments:task-comments", args=[task_data["id"]]), {"body": "Second"})

    response = api_client.get(reverse("comments:task-comments", args=[task_data["id"]]))

    assert response.status_code == status.HTTP_200_OK
    assert [c["body"] for c in response.data["results"]] == ["First", "Second"]


def test_author_can_edit_own_comment(api_client, project_with_task):
    task_data, owner, _member = project_with_task
    _authenticate(api_client, owner)
    created = api_client.post(reverse("comments:task-comments", args=[task_data["id"]]), {"body": "Original"})

    response = api_client.patch(reverse("comments:detail", args=[created.data["id"]]), {"body": "Edited"})

    assert response.status_code == status.HTTP_200_OK
    assert response.data["body"] == "Edited"
    assert response.data["edited_at"] is not None


def test_non_author_cannot_edit_comment(api_client, project_with_task):
    task_data, owner, member = project_with_task
    _authenticate(api_client, owner)
    created = api_client.post(reverse("comments:task-comments", args=[task_data["id"]]), {"body": "Original"})

    _authenticate(api_client, member)
    response = api_client.patch(reverse("comments:detail", args=[created.data["id"]]), {"body": "Hijacked"})

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert Comment.objects.get(id=created.data["id"]).body == "Original"


def test_author_can_delete_own_comment_and_it_disappears_from_list(api_client, project_with_task):
    task_data, owner, _member = project_with_task
    _authenticate(api_client, owner)
    created = api_client.post(reverse("comments:task-comments", args=[task_data["id"]]), {"body": "Temporary"})

    delete_response = api_client.delete(reverse("comments:detail", args=[created.data["id"]]))
    assert delete_response.status_code == status.HTTP_204_NO_CONTENT

    # soft-deleted: row survives (for activity-history coherence) but is
    # excluded from normal reads
    assert Comment.objects.filter(id=created.data["id"]).exists()
    assert Comment.objects.get(id=created.data["id"]).deleted_at is not None

    list_response = api_client.get(reverse("comments:task-comments", args=[task_data["id"]]))
    assert list_response.data["results"] == []


def test_non_author_cannot_delete_comment(api_client, project_with_task):
    task_data, owner, member = project_with_task
    _authenticate(api_client, owner)
    created = api_client.post(reverse("comments:task-comments", args=[task_data["id"]]), {"body": "Protected"})

    _authenticate(api_client, member)
    response = api_client.delete(reverse("comments:detail", args=[created.data["id"]]))

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert Comment.objects.filter(id=created.data["id"], deleted_at__isnull=True).exists()
