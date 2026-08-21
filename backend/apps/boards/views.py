from django.db.models import Count, Prefetch, Q
from django.http import Http404
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.users.permissions import IsEmailVerified

from .models import Board, BoardColumn
from .permissions import can_manage_board, has_board_access
from .selectors import visible_boards_for_user
from .serializers import (
    BoardColumnCreateSerializer,
    BoardColumnReorderSerializer,
    BoardColumnSerializer,
    BoardColumnUpdateSerializer,
    BoardSerializer,
    BoardWithTasksSerializer,
)
from .services import compute_reorder_position, next_append_position

BOARD_PERMISSIONS = [IsAuthenticated, IsEmailVerified]


def _get_visible_board_or_404(request, board_id):
    return get_object_or_404(visible_boards_for_user(request.user), id=board_id)


def _get_visible_column_or_404(request, column_id):
    """A column outside a visible board is treated as not existing — same
    IDOR policy as everywhere else in the app."""
    column = get_object_or_404(BoardColumn.objects.select_related("board__project"), id=column_id)
    if not has_board_access(request.user, column.board):
        raise Http404
    return column


class BoardDetailView(APIView):
    permission_classes = BOARD_PERMISSIONS

    def get(self, request, board_id):
        board = _get_visible_board_or_404(request, board_id)
        return Response(BoardSerializer(board).data)


class BoardFullView(APIView):
    """
    Phase 8 — GET /api/boards/{id}/full/: everything a drag-and-drop board
    view needs in one round-trip. Columns in position order, each with its
    tasks in position order, each task carrying assignees/labels/checklist
    counts/priority/dates/version — the same fields TaskSerializer already
    returns elsewhere, just nested here instead of requiring a follow-up
    per-column fetch.

    Purely additive: GET /api/boards/{id}/ (BoardDetailView, above) is
    completely unchanged, still returns columns without nested tasks.
    """

    permission_classes = BOARD_PERMISSIONS

    def get(self, request, board_id):
        # Local import: apps.tasks.models already imports apps.boards.models
        # (Task.column FK), so importing apps.tasks.models here is safe
        # (no cycle back to apps.boards.models) — done locally anyway to
        # keep this view's dependency direction explicit and contained.
        from apps.tasks.models import Task, TaskAssignee, TaskLabel

        tasks_qs = (
            Task.objects.select_related("created_by", "checklist")
            .prefetch_related(
                Prefetch(
                    "assignees",
                    queryset=TaskAssignee.objects.select_related("user").order_by("assigned_at"),
                ),
                Prefetch(
                    "task_labels",
                    queryset=TaskLabel.objects.select_related("label").order_by("label__name"),
                ),
            )
            .annotate(
                checklist_total_annotated=Count("checklist__items", distinct=True),
                checklist_done_annotated=Count(
                    "checklist__items", filter=Q(checklist__items__is_done=True), distinct=True
                ),
            )
            .order_by("position")
        )
        columns_qs = BoardColumn.objects.order_by("position").prefetch_related(
            Prefetch("tasks", queryset=tasks_qs)
        )
        board = get_object_or_404(
            visible_boards_for_user(request.user).prefetch_related(Prefetch("columns", queryset=columns_qs)),
            id=board_id,
        )
        return Response(BoardWithTasksSerializer(board).data)


class BoardColumnListCreateView(APIView):
    permission_classes = BOARD_PERMISSIONS

    def get(self, request, board_id):
        board = _get_visible_board_or_404(request, board_id)
        columns = board.columns.all()
        return Response(BoardColumnSerializer(columns, many=True).data)

    def post(self, request, board_id):
        board = _get_visible_board_or_404(request, board_id)
        if not can_manage_board(request.user, board):
            return Response(
                {"detail": "Only workspace owners and admins can add columns.", "code": "forbidden"},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = BoardColumnCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        column = BoardColumn.objects.create(
            board=board,
            name=serializer.validated_data["name"],
            position=next_append_position(board),
        )
        return Response(BoardColumnSerializer(column).data, status=status.HTTP_201_CREATED)


class BoardColumnDetailView(APIView):
    permission_classes = BOARD_PERMISSIONS

    def patch(self, request, column_id):
        column = _get_visible_column_or_404(request, column_id)
        if not can_manage_board(request.user, column.board):
            return Response(
                {"detail": "Only workspace owners and admins can rename columns.", "code": "forbidden"},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = BoardColumnUpdateSerializer(column, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(BoardColumnSerializer(column).data)

    def delete(self, request, column_id):
        column = _get_visible_column_or_404(request, column_id)
        if not can_manage_board(request.user, column.board):
            return Response(
                {"detail": "Only workspace owners and admins can delete columns.", "code": "forbidden"},
                status=status.HTTP_403_FORBIDDEN,
            )
        # "Delete columns safely" (original spec, Section 4): refuse rather
        # than silently orphaning or cascading away someone's tasks. The
        # client has to move or delete the tasks first.
        if column.tasks.exists():
            return Response(
                {
                    "detail": "Move or delete this column's tasks before deleting the column.",
                    "code": "column_not_empty",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        column.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class BoardColumnReorderView(APIView):
    permission_classes = BOARD_PERMISSIONS

    def post(self, request, column_id):
        column = _get_visible_column_or_404(request, column_id)
        if not can_manage_board(request.user, column.board):
            return Response(
                {"detail": "Only workspace owners and admins can reorder columns.", "code": "forbidden"},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = BoardColumnReorderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        after_column_id = serializer.validated_data["after_column_id"]

        if after_column_id is not None and str(after_column_id) == str(column.id):
            return Response(
                {"detail": "A column cannot be placed after itself.", "code": "invalid_position"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            new_position = compute_reorder_position(column.board, after_column_id, moving_column_id=column.id)
        except ValueError:
            return Response(
                {"detail": "after_column_id is not a column on this board.", "code": "invalid_after_column"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        column.position = new_position
        column.save(update_fields=["position"])
        return Response(BoardColumnSerializer(column).data)
