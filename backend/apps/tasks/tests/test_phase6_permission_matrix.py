"""
Explicit permission-matrix coverage for the Phase 6 features (assignment,
labels, checklists), across the five roles the Phase 1 architecture doc's
Section 6.1 rule distinguishes:

  - OWNER                                    -> full access
  - ADMIN (implicit access, no ProjectMembership row)  -> full access
  - MEMBER with an explicit ProjectMembership row       -> full access
  - MEMBER without a ProjectMembership row              -> 404
  - outsider (not even a workspace member)              -> 404

Other test files already cover the individual behaviors in depth (create/
update/delete, IDOR on cross-project references, etc.) — this file is
specifically about proving the role matrix holds for each feature area,
per the Phase 6 correction request.
"""
import pytest
from django.urls import reverse
from rest_framework import status

from apps.boards.models import Board
from apps.projects.models import ProjectMembership
from apps.users.models import User
from apps.workspaces.models import Workspace, WorkspaceMembership, WorkspaceRole

pytestmark = pytest.mark.django_db

PASSWORD = "TestPass123!"

ALLOWED = ["owner", "admin", "member_in"]
DENIED = ["member_out", "outsider"]


def _make_user(email, display_name, verified=True):
    user = User.objects.create_user(email=email, password=PASSWORD, display_name=display_name)
    if verified:
        user.is_email_verified = True
        user.save(update_fields=["is_email_verified"])
    return user


def _authenticate(api_client, user):
    api_client.force_authenticate(user=user)


@pytest.fixture
def matrix_setup(api_client):
    owner = _make_user("matrix_owner@example.com", "Owner")
    admin = _make_user("matrix_admin@example.com", "Admin")  # implicit access, no ProjectMembership
    member_in = _make_user("matrix_member_in@example.com", "Member In")  # explicit ProjectMembership
    member_out = _make_user("matrix_member_out@example.com", "Member Out")  # workspace MEMBER, no ProjectMembership
    outsider = _make_user("matrix_outsider@example.com", "Outsider")  # not even a workspace member

    _authenticate(api_client, owner)
    ws = api_client.post(reverse("workspaces:list-create"), {"name": "Matrix Workspace"})
    workspace = Workspace.objects.get(id=ws.data["id"])
    WorkspaceMembership.objects.create(workspace=workspace, user=admin, role=WorkspaceRole.ADMIN)
    WorkspaceMembership.objects.create(workspace=workspace, user=member_in, role=WorkspaceRole.MEMBER)
    WorkspaceMembership.objects.create(workspace=workspace, user=member_out, role=WorkspaceRole.MEMBER)

    proj = api_client.post(
        reverse("projects:list-create"), {"workspace_id": str(workspace.id), "name": "Matrix Project"}
    )
    ProjectMembership.objects.create(project_id=proj.data["id"], user=member_in, added_by=owner)

    board = Board.objects.get(id=proj.data["board_id"])
    column = board.columns.first()
    task = api_client.post(reverse("tasks:list-create"), {"column_id": str(column.id), "title": "Matrix Task"})

    actors = {
        "owner": owner,
        "admin": admin,
        "member_in": member_in,
        "member_out": member_out,
        "outsider": outsider,
    }
    return proj.data, task.data, actors


# --- assignment -------------------------------------------------------------


@pytest.mark.parametrize("actor_key", ALLOWED)
def test_assignment_allowed_for(api_client, matrix_setup, actor_key):
    _project_data, task_data, actors = matrix_setup
    _authenticate(api_client, actors[actor_key])

    response = api_client.post(
        reverse("tasks:assignees", args=[task_data["id"]]), {"user_id": str(actors["member_in"].id)}
    )

    assert response.status_code == status.HTTP_201_CREATED


@pytest.mark.parametrize("actor_key", DENIED)
def test_assignment_denied_for(api_client, matrix_setup, actor_key):
    _project_data, task_data, actors = matrix_setup
    _authenticate(api_client, actors[actor_key])

    response = api_client.post(
        reverse("tasks:assignees", args=[task_data["id"]]), {"user_id": str(actors["member_in"].id)}
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND


# --- labels -------------------------------------------------------------


@pytest.mark.parametrize("actor_key", ALLOWED)
def test_label_creation_allowed_for(api_client, matrix_setup, actor_key):
    project_data, _task_data, actors = matrix_setup
    _authenticate(api_client, actors[actor_key])

    response = api_client.post(
        reverse("tasks:project-labels", args=[project_data["id"]]), {"name": f"Label by {actor_key}"}
    )

    assert response.status_code == status.HTTP_201_CREATED


@pytest.mark.parametrize("actor_key", DENIED)
def test_label_creation_denied_for(api_client, matrix_setup, actor_key):
    project_data, _task_data, actors = matrix_setup
    _authenticate(api_client, actors[actor_key])

    response = api_client.post(
        reverse("tasks:project-labels", args=[project_data["id"]]), {"name": f"Label by {actor_key}"}
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND


# --- checklist -------------------------------------------------------------


@pytest.mark.parametrize("actor_key", ALLOWED)
def test_checklist_item_add_allowed_for(api_client, matrix_setup, actor_key):
    _project_data, task_data, actors = matrix_setup
    _authenticate(api_client, actors[actor_key])

    response = api_client.post(
        reverse("tasks:checklist", args=[task_data["id"]]), {"text": f"Item by {actor_key}"}
    )

    assert response.status_code == status.HTTP_201_CREATED


@pytest.mark.parametrize("actor_key", DENIED)
def test_checklist_item_add_denied_for(api_client, matrix_setup, actor_key):
    _project_data, task_data, actors = matrix_setup
    _authenticate(api_client, actors[actor_key])

    response = api_client.post(
        reverse("tasks:checklist", args=[task_data["id"]]), {"text": f"Item by {actor_key}"}
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND
