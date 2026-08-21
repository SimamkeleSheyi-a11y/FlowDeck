from django.db.models import Count, Prefetch, Q
from django.http import Http404
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.activity.models import ActivityEventType
from apps.activity.services import log_activity
from apps.boards.models import BoardColumn
from apps.projects.permissions import has_project_access
from apps.projects.selectors import visible_projects_for_user
from apps.users.models import User
from apps.users.permissions import IsEmailVerified

from .models import Checklist, ChecklistItem, Label, Task, TaskAssignee, TaskLabel, TaskPriority
from .selectors import visible_tasks_for_user
from .serializers import (
    ChecklistItemCreateSerializer,
    ChecklistItemReorderSerializer,
    ChecklistItemSerializer,
    ChecklistItemUpdateSerializer,
    ChecklistSerializer,
    LabelCreateSerializer,
    LabelSerializer,
    LabelUpdateSerializer,
    TaskAssigneeSerializer,
    TaskAssignSerializer,
    TaskCreateSerializer,
    TaskMoveSerializer,
    TaskSerializer,
    TaskUpdateSerializer,
)
from .services import (
    compute_checklist_item_position,
    compute_move_position,
    get_or_create_checklist,
    next_append_position,
    next_checklist_item_position,
)

TASK_PERMISSIONS = [IsAuthenticated, IsEmailVerified]


def _get_visible_project_or_404(request, project_id):
    """Same 404-not-403 IDOR policy used throughout this project — a
    project outside visible_projects_for_user() is treated as not
    existing. Kept local rather than importing apps.projects.views'
    private helper of the same purpose."""
    return get_object_or_404(visible_projects_for_user(request.user), id=project_id)


def _get_visible_task_or_404(request, task_id):
    return get_object_or_404(visible_tasks_for_user(request.user), id=task_id)


def _get_visible_checklist_item_or_404(request, item_id):
    """Same 404-not-403 IDOR policy as everywhere else — a checklist item
    outside a project the requester can access is treated as not existing."""
    item = get_object_or_404(ChecklistItem.objects.select_related("checklist__task__project"), id=item_id)
    if not has_project_access(request.user, item.checklist.task.project):
        raise Http404
    return item


def _get_accessible_column_or_404(request, column_id, project=None):
    """
    Resolves a column the requester can act in. If `project` is given, the
    column must belong to THAT project's board — used by the move endpoint
    so a task can't jump to a different project's board; a client trying
    that gets a plain 404 (the column "isn't there" from this task's
    point of view), not a 400 revealing that a matching column exists
    elsewhere.
    """
    qs = BoardColumn.objects.select_related("board__project")
    if project is not None:
        qs = qs.filter(board__project=project)
    column = get_object_or_404(qs, id=column_id)
    if not has_project_access(request.user, column.board.project):
        raise Http404
    return column


class TaskListCreateView(APIView):
    permission_classes = TASK_PERMISSIONS
    pagination_class = LimitOffsetPagination

    def get(self, request):
        tasks = visible_tasks_for_user(request.user).select_related("column", "project", "created_by", "checklist")

        project_id = request.query_params.get("project")
        if project_id:
            tasks = tasks.filter(project_id=project_id)

        column_id = request.query_params.get("column")
        if column_id:
            tasks = tasks.filter(column_id=column_id)

        priority = request.query_params.get("priority")
        if priority in dict(TaskPriority.choices):
            tasks = tasks.filter(priority=priority)

        is_completed = request.query_params.get("is_completed")
        if is_completed is not None:
            tasks = tasks.filter(is_completed=is_completed.lower() == "true")

        assignee_id = request.query_params.get("assignee")
        if assignee_id == "me":
            tasks = tasks.filter(assignees__user=request.user)
        elif assignee_id:
            tasks = tasks.filter(assignees__user_id=assignee_id)

        # Prefetch assignees/labels and annotate checklist counts so
        # TaskSerializer's new Phase 6 fields don't turn this into an N+1 —
        # same discipline as the Phase 3 correction that fixed the
        # workspace list endpoint the same way.
        tasks = (
            tasks.distinct()
            .prefetch_related(
                Prefetch("assignees", queryset=TaskAssignee.objects.select_related("user").order_by("assigned_at")),
                Prefetch("task_labels", queryset=TaskLabel.objects.select_related("label").order_by("label__name")),
            )
            .annotate(
                checklist_total_annotated=Count("checklist__items", distinct=True),
                checklist_done_annotated=Count(
                    "checklist__items", filter=Q(checklist__items__is_done=True), distinct=True
                ),
            )
            .order_by("position")
        )

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(tasks, request, view=self)
        serializer = TaskSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    def post(self, request):
        serializer = TaskCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        column = _get_accessible_column_or_404(request, data["column_id"])
        project = column.board.project

        task = Task.objects.create(
            column=column,
            project=project,
            title=data["title"],
            description=data.get("description", ""),
            priority=data.get("priority", TaskPriority.MEDIUM),
            start_date=data.get("start_date"),
            due_date=data.get("due_date"),
            position=next_append_position(column),
            created_by=request.user,
        )
        log_activity(
            actor=request.user,
            event_type=ActivityEventType.TASK_CREATED,
            workspace=project.workspace,
            project=project,
            task=task,
        )
        return Response(TaskSerializer(task).data, status=status.HTTP_201_CREATED)


class TaskDetailView(APIView):
    permission_classes = TASK_PERMISSIONS

    def get(self, request, task_id):
        task = _get_visible_task_or_404(request, task_id)
        return Response(TaskSerializer(task).data)

    def patch(self, request, task_id):
        task = _get_visible_task_or_404(request, task_id)
        old_priority = task.priority
        old_due_date = task.due_date
        old_is_completed = task.is_completed

        serializer = TaskUpdateSerializer(task, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        # Bumped separately from the serializer's own save so this applies
        # uniformly to any field edit, not just column/position changes —
        # Phase 1 architecture doc, Section 5.3: "incremented on every
        # mutating update".
        task.version += 1
        task.save(update_fields=["version"])

        # Log the most specific event that actually changed, matching the
        # original spec's example activity lines ("Priority changed from
        # Medium to High.", "Task completed.") — falls back to a generic
        # TASK_UPDATED only if none of the specifically-tracked fields did
        # (e.g. just a title/description edit).
        workspace = task.project.workspace
        logged_something_specific = False
        if task.priority != old_priority:
            log_activity(
                actor=request.user,
                event_type=ActivityEventType.TASK_PRIORITY_CHANGED,
                workspace=workspace,
                project=task.project,
                task=task,
                metadata={"from": old_priority, "to": task.priority},
            )
            logged_something_specific = True
        if task.due_date != old_due_date:
            log_activity(
                actor=request.user,
                event_type=ActivityEventType.TASK_DUE_DATE_CHANGED,
                workspace=workspace,
                project=task.project,
                task=task,
                metadata={
                    "from": old_due_date.isoformat() if old_due_date else None,
                    "to": task.due_date.isoformat() if task.due_date else None,
                },
            )
            logged_something_specific = True
        if task.is_completed != old_is_completed:
            log_activity(
                actor=request.user,
                event_type=ActivityEventType.TASK_COMPLETED if task.is_completed else ActivityEventType.TASK_REOPENED,
                workspace=workspace,
                project=task.project,
                task=task,
            )
            logged_something_specific = True
        if not logged_something_specific:
            log_activity(
                actor=request.user,
                event_type=ActivityEventType.TASK_UPDATED,
                workspace=workspace,
                project=task.project,
                task=task,
            )

        return Response(TaskSerializer(task).data)

    def delete(self, request, task_id):
        task = _get_visible_task_or_404(request, task_id)
        # Logged before delete() — Task uses SET_NULL on ActivityEvent.task,
        # but logging first means this specific event still carries the
        # live FK at write time rather than immediately becoming null.
        log_activity(
            actor=request.user,
            event_type=ActivityEventType.TASK_DELETED,
            workspace=task.project.workspace,
            project=task.project,
            task=task,
            metadata={"title": task.title},
        )
        task.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class TaskMoveView(APIView):
    """
    Column/position change with optimistic-concurrency detection (Phase 1
    architecture doc, Section 5.3). Default behavior (strict omitted or
    false) is accept-and-flag: if the client's submitted `version` no
    longer matches the task's current version, the move still applies
    (last-write-wins) but the response carries `"conflict": true` plus the
    full canonical task state, so the frontend can show a brief
    reconciliation notice and refresh its local copy instead of silently
    trusting its own optimistic move.

    Phase 8 adds `strict: true` as an opt-in: with it set, a stale version
    returns `409 CONFLICT` (with the current canonical state under
    `"current"`) instead of applying the move — the task's column,
    position, and version are left completely untouched, and no activity
    event is logged. Every existing caller that doesn't send `strict`
    keeps the original Phase 5 behavior exactly.
    """

    permission_classes = TASK_PERMISSIONS

    def post(self, request, task_id):
        task = _get_visible_task_or_404(request, task_id)
        serializer = TaskMoveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        # Scoped to task.project — a task can only move between columns on
        # its own project's board, never to another project's board.
        target_column = _get_accessible_column_or_404(request, data["column_id"], project=task.project)

        if data["after_task_id"] is not None and str(data["after_task_id"]) == str(task.id):
            return Response(
                {"detail": "A task cannot be placed after itself.", "code": "invalid_position"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            new_position = compute_move_position(target_column, data["after_task_id"], moving_task_id=task.id)
        except ValueError:
            return Response(
                {"detail": "after_task_id is not a task in the target column.", "code": "invalid_after_task"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        conflict = data["version"] != task.version

        # Phase 8: opt-in strict mode. Checked before any mutation — the
        # task's column/position/version are completely untouched and no
        # activity event is logged when this returns. Default (strict
        # omitted or False) falls through to the unchanged Phase 5
        # accept-and-flag behavior below.
        if data["strict"] and conflict:
            return Response(
                {
                    "detail": "This task was changed since you last loaded it — refresh and try again.",
                    "code": "version_conflict",
                    "current": TaskSerializer(task).data,
                },
                status=status.HTTP_409_CONFLICT,
            )

        old_column = task.column

        task.column = target_column
        task.position = new_position
        task.version += 1
        task.save(update_fields=["column", "position", "version", "updated_at"])

        log_activity(
            actor=request.user,
            event_type=ActivityEventType.TASK_MOVED,
            workspace=task.project.workspace,
            project=task.project,
            task=task,
            metadata={"from_column": old_column.name, "to_column": target_column.name},
        )

        response_data = TaskSerializer(task).data
        response_data["conflict"] = conflict
        return Response(response_data, status=status.HTTP_200_OK)


class TaskAssigneesView(APIView):
    """POST assigns a user to the task; any project member may assign, but
    only to someone who themselves has project access — "prevent assigning
    users who are not members of the appropriate workspace/project" from
    the original spec, enforced via the same has_project_access check used
    for the task itself."""

    permission_classes = TASK_PERMISSIONS

    def post(self, request, task_id):
        task = _get_visible_task_or_404(request, task_id)
        serializer = TaskAssignSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        target_user_id = serializer.validated_data["user_id"]

        target_user = get_object_or_404(User, id=target_user_id)
        if not has_project_access(target_user, task.project):
            return Response(
                {
                    "detail": "That user is not a member of this task's workspace/project.",
                    "code": "not_project_member",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        assignment, created = TaskAssignee.objects.get_or_create(
            task=task, user=target_user, defaults={"assigned_by": request.user}
        )
        if not created:
            return Response(
                {"detail": "That user is already assigned to this task.", "code": "already_assigned"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        log_activity(
            actor=request.user,
            event_type=ActivityEventType.TASK_ASSIGNED,
            workspace=task.project.workspace,
            project=task.project,
            task=task,
            target_type="user",
            target_id=target_user.id,
            metadata={"assignee_display_name": target_user.display_name},
        )
        return Response(TaskAssigneeSerializer(assignment).data, status=status.HTTP_201_CREATED)


class TaskAssigneeDetailView(APIView):
    permission_classes = TASK_PERMISSIONS

    def delete(self, request, task_id, user_id):
        task = _get_visible_task_or_404(request, task_id)
        assignment = get_object_or_404(TaskAssignee, task=task, user_id=user_id)
        log_activity(
            actor=request.user,
            event_type=ActivityEventType.TASK_UNASSIGNED,
            workspace=task.project.workspace,
            project=task.project,
            task=task,
            target_type="user",
            target_id=user_id,
        )
        assignment.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class LabelListCreateView(APIView):
    permission_classes = TASK_PERMISSIONS

    def get(self, request, project_id):
        project = _get_visible_project_or_404(request, project_id)
        return Response(LabelSerializer(project.labels.all(), many=True).data)

    def post(self, request, project_id):
        project = _get_visible_project_or_404(request, project_id)
        serializer = LabelCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        if project.labels.filter(name__iexact=serializer.validated_data["name"]).exists():
            return Response(
                {"detail": "A label with that name already exists on this project.", "code": "duplicate_label"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        label = Label.objects.create(project=project, **serializer.validated_data)
        return Response(LabelSerializer(label).data, status=status.HTTP_201_CREATED)


class LabelDetailView(APIView):
    permission_classes = TASK_PERMISSIONS

    def _get_visible_label_or_404(self, request, label_id):
        label = get_object_or_404(Label.objects.select_related("project"), id=label_id)
        if not has_project_access(request.user, label.project):
            raise Http404
        return label

    def patch(self, request, label_id):
        label = self._get_visible_label_or_404(request, label_id)
        serializer = LabelUpdateSerializer(label, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        new_name = serializer.validated_data.get("name")
        if new_name is not None:
            # Checked here, before save(), so a rename to an existing name
            # in the same project comes back as a controlled 400 — not the
            # unique_label_name_per_project DB constraint raising an
            # uncaught IntegrityError. Case-insensitive, excludes this
            # label itself (so re-saving with only a casing tweak, or an
            # unrelated color-only PATCH, never spuriously fails), and
            # scoped to this project only — the same name stays fine on a
            # different project (a different unique_together pair).
            duplicate = (
                Label.objects.filter(project=label.project, name__iexact=new_name)
                .exclude(id=label.id)
                .exists()
            )
            if duplicate:
                return Response(
                    {
                        "detail": "A label with that name already exists on this project.",
                        "code": "duplicate_label",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        serializer.save()
        return Response(LabelSerializer(label).data)

    def delete(self, request, label_id):
        label = self._get_visible_label_or_404(request, label_id)
        label.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class TaskLabelsView(APIView):
    permission_classes = TASK_PERMISSIONS

    def post(self, request, task_id):
        task = _get_visible_task_or_404(request, task_id)
        label_id = request.data.get("label_id")
        label = get_object_or_404(Label, id=label_id, project=task.project)

        _tasklabel, created = TaskLabel.objects.get_or_create(task=task, label=label)
        if not created:
            return Response(
                {"detail": "That label is already on this task.", "code": "already_labeled"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        log_activity(
            actor=request.user,
            event_type=ActivityEventType.LABEL_ADDED,
            workspace=task.project.workspace,
            project=task.project,
            task=task,
            target_type="label",
            target_id=label.id,
            metadata={"label_name": label.name},
        )
        return Response(LabelSerializer(label).data, status=status.HTTP_201_CREATED)


class TaskLabelDetailView(APIView):
    permission_classes = TASK_PERMISSIONS

    def delete(self, request, task_id, label_id):
        task = _get_visible_task_or_404(request, task_id)
        tasklabel = get_object_or_404(TaskLabel, task=task, label_id=label_id)
        log_activity(
            actor=request.user,
            event_type=ActivityEventType.LABEL_REMOVED,
            workspace=task.project.workspace,
            project=task.project,
            task=task,
            target_type="label",
            target_id=label_id,
            metadata={"label_name": tasklabel.label.name},
        )
        tasklabel.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class TaskChecklistView(APIView):
    """
    Singular checklist per task (Phase 1 API map: `/tasks/{id}/checklist/`,
    not `/checklists/`) — created lazily on first GET or POST rather than
    needing a separate creation step.
    """

    permission_classes = TASK_PERMISSIONS

    def get(self, request, task_id):
        task = _get_visible_task_or_404(request, task_id)
        checklist = get_or_create_checklist(task)
        return Response(ChecklistSerializer(checklist).data)

    def post(self, request, task_id):
        task = _get_visible_task_or_404(request, task_id)
        serializer = ChecklistItemCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        checklist = get_or_create_checklist(task)
        item = ChecklistItem.objects.create(
            checklist=checklist,
            text=serializer.validated_data["text"],
            position=next_checklist_item_position(checklist),
        )
        log_activity(
            actor=request.user,
            event_type=ActivityEventType.CHECKLIST_ITEM_ADDED,
            workspace=task.project.workspace,
            project=task.project,
            task=task,
            target_type="checklist_item",
            target_id=item.id,
            metadata={"text": item.text},
        )
        return Response(ChecklistItemSerializer(item).data, status=status.HTTP_201_CREATED)


class ChecklistItemDetailView(APIView):
    permission_classes = TASK_PERMISSIONS

    def patch(self, request, item_id):
        item = _get_visible_checklist_item_or_404(request, item_id)
        was_done = item.is_done
        serializer = ChecklistItemUpdateSerializer(item, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        if item.is_done and not was_done:
            task = item.checklist.task
            log_activity(
                actor=request.user,
                event_type=ActivityEventType.CHECKLIST_ITEM_COMPLETED,
                workspace=task.project.workspace,
                project=task.project,
                task=task,
                target_type="checklist_item",
                target_id=item.id,
                metadata={"text": item.text},
            )
        return Response(ChecklistItemSerializer(item).data)

    def delete(self, request, item_id):
        item = _get_visible_checklist_item_or_404(request, item_id)
        item.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ChecklistItemReorderView(APIView):
    """
    Gap-based reorder within a single checklist item's own checklist — same
    scheme as BoardColumnReorderView and TaskMoveView. There's no parameter
    anywhere in this request that names a *different* checklist/task/
    project to move into, so cross-task or cross-project movement isn't
    just rejected, it's not an expressible request in the first place.
    """

    permission_classes = TASK_PERMISSIONS

    def post(self, request, item_id):
        item = _get_visible_checklist_item_or_404(request, item_id)
        serializer = ChecklistItemReorderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        after_item_id = serializer.validated_data["after_item_id"]

        if after_item_id is not None and str(after_item_id) == str(item.id):
            return Response(
                {"detail": "An item cannot be placed after itself.", "code": "invalid_position"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            new_position = compute_checklist_item_position(item.checklist, after_item_id, moving_item_id=item.id)
        except ValueError:
            return Response(
                {
                    "detail": "after_item_id is not an item in this checklist.",
                    "code": "invalid_after_item",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        item.position = new_position
        item.save(update_fields=["position"])
        return Response(ChecklistItemSerializer(item).data)
