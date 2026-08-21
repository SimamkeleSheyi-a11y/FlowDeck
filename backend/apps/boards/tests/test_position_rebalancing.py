import pytest
from django.urls import reverse
from rest_framework import status

from apps.boards.models import Board, BoardColumn
from apps.boards.services import MIN_GAP
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
def board_owner(api_client):
    owner = _make_user("rebalance_owner@example.com", "Owner")
    _authenticate(api_client, owner)
    ws = api_client.post(reverse("workspaces:list-create"), {"name": "Rebalance Workspace"})
    workspace = Workspace.objects.get(id=ws.data["id"])
    proj = api_client.post(reverse("projects:list-create"), {"workspace_id": str(workspace.id), "name": "Rebalance Project"})
    board = Board.objects.get(id=proj.data["board_id"])
    return board, owner


def test_rebalance_triggers_when_gap_too_small(api_client, board_owner):
    board, owner = board_owner
    _authenticate(api_client, owner)
    columns = list(board.columns.order_by("position"))
    backlog = columns[0]

    # Simulate the end-state of many prior narrowing reorders directly,
    # rather than looping hundreds of times: two adjacent columns with a
    # gap far below MIN_GAP.
    tight = BoardColumn.objects.create(board=board, name="Tight", position=backlog.position + MIN_GAP / 10)

    new_column = api_client.post(reverse("boards:columns", args=[board.id]), {"name": "Inserted"})
    response = api_client.post(
        reverse("boards:column-reorder", args=[new_column.data["id"]]),
        {"after_column_id": str(backlog.id)},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK

    # After the rebalance, every column on the board must have a distinct
    # position, and adjacent gaps must be healthy again (not sub-MIN_GAP).
    positions = list(board.columns.order_by("position").values_list("position", flat=True))
    assert len(positions) == len(set(positions))  # no duplicates
    gaps = [b - a for a, b in zip(positions, positions[1:])]
    assert all(gap >= MIN_GAP * 1000 for gap in gaps)

    # order preserved: the inserted column still sits right after backlog
    ordered_names = list(board.columns.order_by("position").values_list("name", flat=True))
    backlog_index = ordered_names.index("Backlog")
    assert ordered_names[backlog_index + 1] == "Inserted"


def test_repeated_reorders_never_produce_duplicate_or_unstable_positions(api_client, board_owner):
    board, owner = board_owner
    _authenticate(api_client, owner)
    columns = list(board.columns.order_by("position"))
    backlog = columns[0]

    # Real, repeated reorder operations (not simulated) — each new column
    # inserted immediately after "Backlog" becomes the new tightest
    # neighbor for the next one, halving that gap every time. Comfortably
    # enough iterations to exhaust float precision from the initial
    # POSITION_GAP (1000.0) well past MIN_GAP (1e-6) — a rebalance should
    # kick in transparently partway through, and every single call must
    # still succeed with 200.
    for i in range(40):
        created = api_client.post(reverse("boards:columns", args=[board.id]), {"name": f"Loop {i}"})
        response = api_client.post(
            reverse("boards:column-reorder", args=[created.data["id"]]),
            {"after_column_id": str(backlog.id)},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK, f"iteration {i} failed: {response.data}"

    positions = list(board.columns.order_by("position").values_list("position", flat=True))
    assert len(positions) == len(set(positions))  # still no duplicates after 40 rounds
    assert positions == sorted(positions)  # strictly increasing, no corruption
