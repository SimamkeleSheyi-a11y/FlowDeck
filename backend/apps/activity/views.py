from django.shortcuts import get_object_or_404
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.tasks.selectors import visible_tasks_for_user
from apps.users.permissions import IsEmailVerified

from .serializers import ActivityEventSerializer


class TaskActivityView(APIView):
    """
    GET /api/tasks/{id}/activity/ — the task's history, newest first
    (ActivityEvent.Meta.ordering). Read-only; nothing here ever accepts
    activity data as input (Phase 1 doc, Section 8).
    """

    permission_classes = [IsAuthenticated, IsEmailVerified]
    pagination_class = LimitOffsetPagination

    def get(self, request, task_id):
        task = get_object_or_404(visible_tasks_for_user(request.user), id=task_id)
        events = task.activity_events.select_related("actor").all()

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(events, request, view=self)
        serializer = ActivityEventSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)
