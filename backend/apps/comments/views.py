from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.activity.models import ActivityEventType
from apps.activity.services import log_activity
from apps.tasks.selectors import visible_tasks_for_user
from apps.users.permissions import IsEmailVerified

from .models import Comment
from .permissions import can_modify_comment, has_comment_thread_access
from .serializers import CommentCreateSerializer, CommentSerializer, CommentUpdateSerializer

COMMENT_PERMISSIONS = [IsAuthenticated, IsEmailVerified]


def _get_visible_task_or_404(request, task_id):
    return get_object_or_404(visible_tasks_for_user(request.user), id=task_id)


def _get_visible_comment_or_404(request, comment_id):
    """Same 404-not-403 IDOR policy as everywhere else. Soft-deleted
    comments are excluded — they're gone from every normal read path, only
    the ActivityEvent referencing them still points at a real row."""
    comment = get_object_or_404(
        Comment.objects.select_related("task__project__workspace").filter(deleted_at__isnull=True),
        id=comment_id,
    )
    if not has_comment_thread_access(request.user, comment.task):
        raise Http404
    return comment


class TaskCommentsView(APIView):
    permission_classes = COMMENT_PERMISSIONS
    pagination_class = LimitOffsetPagination

    def get(self, request, task_id):
        task = _get_visible_task_or_404(request, task_id)
        comments = task.comments.filter(deleted_at__isnull=True).select_related("author")
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(comments, request, view=self)
        serializer = CommentSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    def post(self, request, task_id):
        task = _get_visible_task_or_404(request, task_id)
        serializer = CommentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        comment = Comment.objects.create(task=task, author=request.user, body=serializer.validated_data["body"])

        log_activity(
            actor=request.user,
            event_type=ActivityEventType.COMMENT_ADDED,
            workspace=task.project.workspace,
            project=task.project,
            task=task,
            target_type="comment",
            target_id=comment.id,
        )

        return Response(CommentSerializer(comment).data, status=status.HTTP_201_CREATED)


class CommentDetailView(APIView):
    permission_classes = COMMENT_PERMISSIONS

    def patch(self, request, comment_id):
        comment = _get_visible_comment_or_404(request, comment_id)
        if not can_modify_comment(request.user, comment):
            return Response(
                {"detail": "You can only edit your own comments.", "code": "forbidden"},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = CommentUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        comment.body = serializer.validated_data["body"]
        comment.edited_at = timezone.now()
        comment.save(update_fields=["body", "edited_at", "updated_at"])

        log_activity(
            actor=request.user,
            event_type=ActivityEventType.COMMENT_EDITED,
            workspace=comment.task.project.workspace,
            project=comment.task.project,
            task=comment.task,
            target_type="comment",
            target_id=comment.id,
        )

        return Response(CommentSerializer(comment).data)

    def delete(self, request, comment_id):
        comment = _get_visible_comment_or_404(request, comment_id)
        if not can_modify_comment(request.user, comment):
            return Response(
                {"detail": "You can only delete your own comments.", "code": "forbidden"},
                status=status.HTTP_403_FORBIDDEN,
            )
        comment.deleted_at = timezone.now()
        comment.save(update_fields=["deleted_at"])

        log_activity(
            actor=request.user,
            event_type=ActivityEventType.COMMENT_DELETED,
            workspace=comment.task.project.workspace,
            project=comment.task.project,
            task=comment.task,
            target_type="comment",
            target_id=comment.id,
        )

        return Response(status=status.HTTP_204_NO_CONTENT)
