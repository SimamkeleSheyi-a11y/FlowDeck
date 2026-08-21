from django.db import transaction
from django.db.models import Prefetch
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
from apps.boards.services import create_default_board
from apps.users.permissions import IsEmailVerified
from apps.workspaces.models import Workspace, WorkspaceMembership, WorkspaceRole
from apps.workspaces.permissions import get_membership as get_workspace_membership

from .models import Project, ProjectMembership
from .permissions import can_manage_project, get_workspace_role
from .selectors import visible_projects_for_user
from .serializers import (
    ProjectCreateSerializer,
    ProjectMemberAddSerializer,
    ProjectMembershipSerializer,
    ProjectSerializer,
    ProjectUpdateSerializer,
)

# Same policy as the workspaces app (Phase 3 correction #5): every
# authenticated project endpoint requires a verified email. There's no
# unauthenticated project endpoint at all, so unlike WORKSPACE_PERMISSIONS
# there's no exception list here.
PROJECT_PERMISSIONS = [IsAuthenticated, IsEmailVerified]


def _get_user_workspace_or_404(request, workspace_id):
    """
    Same 404-not-403 IDOR policy as apps/workspaces/views.py's private
    helper of the same name — duplicated rather than imported across apps
    to avoid depending on another app's view-layer internals; both read
    from the same WorkspaceMembership source of truth.
    """
    workspace = get_object_or_404(Workspace, id=workspace_id)
    if get_workspace_membership(request.user, workspace) is None:
        raise Http404
    return workspace


def _get_visible_project_or_404(request, project_id):
    """A project outside visible_projects_for_user() is treated as not
    existing — same IDOR policy as everywhere else in the app."""
    return get_object_or_404(visible_projects_for_user(request.user), id=project_id)


class ProjectListCreateView(APIView):
    permission_classes = PROJECT_PERMISSIONS
    pagination_class = LimitOffsetPagination

    def get(self, request):
        projects = visible_projects_for_user(request.user).select_related("workspace")

        if request.query_params.get("include_archived") != "true":
            projects = projects.filter(archived_at__isnull=True)

        workspace_id = request.query_params.get("workspace")
        if workspace_id:
            projects = projects.filter(workspace_id=workspace_id)

        # Same N+1 fix as WorkspaceListCreateView (Phase 3 correction #4):
        # attach only this user's ProjectMembership row per project via
        # Prefetch(to_attr=...) instead of querying per object in
        # get_am_i_a_project_member.
        my_membership_qs = ProjectMembership.objects.filter(user=request.user)
        projects = projects.prefetch_related(
            Prefetch("memberships", queryset=my_membership_qs, to_attr="my_memberships")
        ).order_by("-created_at")

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(projects, request, view=self)
        serializer = ProjectSerializer(page, many=True, context={"request": request})
        return paginator.get_paginated_response(serializer.data)

    def post(self, request):
        serializer = ProjectCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        workspace = _get_user_workspace_or_404(request, serializer.validated_data["workspace_id"])
        if get_workspace_role(request.user, workspace) not in (WorkspaceRole.OWNER, WorkspaceRole.ADMIN):
            return Response(
                {"detail": "Only workspace owners and admins can create projects.", "code": "forbidden"},
                status=status.HTTP_403_FORBIDDEN,
            )

        with transaction.atomic():
            project = Project.objects.create(
                workspace=workspace,
                name=serializer.validated_data["name"],
                description=serializer.validated_data.get("description", ""),
                created_by=request.user,
            )
            create_default_board(project)
        log_activity(
            actor=request.user,
            event_type=ActivityEventType.PROJECT_CREATED,
            workspace=workspace,
            project=project,
        )
        return Response(
            ProjectSerializer(project, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class ProjectDetailView(APIView):
    permission_classes = PROJECT_PERMISSIONS

    def get(self, request, project_id):
        project = _get_visible_project_or_404(request, project_id)
        return Response(ProjectSerializer(project, context={"request": request}).data)

    def patch(self, request, project_id):
        project = _get_visible_project_or_404(request, project_id)
        if not can_manage_project(request.user, project):
            return Response(
                {"detail": "Only workspace owners and admins can edit this project.", "code": "forbidden"},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = ProjectUpdateSerializer(project, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(ProjectSerializer(project, context={"request": request}).data)

    def delete(self, request, project_id):
        project = _get_visible_project_or_404(request, project_id)
        if not can_manage_project(request.user, project):
            return Response(
                {"detail": "Only workspace owners and admins can delete this project.", "code": "forbidden"},
                status=status.HTTP_403_FORBIDDEN,
            )
        # Nothing downstream references Project yet (boards/tasks arrive in
        # Phase 5, ActivityEvent in Phase 7), so a hard delete is safe for
        # now — revisit the "don't cascade-delete historical records"
        # concern from the Phase 1 doc once those exist.
        project.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ProjectArchiveView(APIView):
    permission_classes = PROJECT_PERMISSIONS

    def post(self, request, project_id):
        project = _get_visible_project_or_404(request, project_id)
        if not can_manage_project(request.user, project):
            return Response(
                {"detail": "Only workspace owners and admins can archive this project.", "code": "forbidden"},
                status=status.HTTP_403_FORBIDDEN,
            )
        project.archived_at = timezone.now()
        project.save(update_fields=["archived_at", "updated_at"])
        return Response(ProjectSerializer(project, context={"request": request}).data)


class ProjectUnarchiveView(APIView):
    permission_classes = PROJECT_PERMISSIONS

    def post(self, request, project_id):
        project = _get_visible_project_or_404(request, project_id)
        if not can_manage_project(request.user, project):
            return Response(
                {"detail": "Only workspace owners and admins can unarchive this project.", "code": "forbidden"},
                status=status.HTTP_403_FORBIDDEN,
            )
        project.archived_at = None
        project.save(update_fields=["archived_at", "updated_at"])
        return Response(ProjectSerializer(project, context={"request": request}).data)


class ProjectMembersView(APIView):
    permission_classes = PROJECT_PERMISSIONS

    def get(self, request, project_id):
        project = _get_visible_project_or_404(request, project_id)
        memberships = project.memberships.select_related("user").order_by("joined_at")
        return Response(ProjectMembershipSerializer(memberships, many=True).data)

    def post(self, request, project_id):
        project = _get_visible_project_or_404(request, project_id)
        if not can_manage_project(request.user, project):
            return Response(
                {"detail": "Only workspace owners and admins can add project members.", "code": "forbidden"},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = ProjectMemberAddSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        target_user_id = serializer.validated_data["user_id"]

        # Can't add someone to a project unless they already belong to the
        # project's workspace — mirrors the "prevent assigning users who
        # aren't members of the appropriate workspace/project" rule from
        # the original task spec (applies here as much as it will to task
        # assignment in Phase 6).
        if not WorkspaceMembership.objects.filter(workspace=project.workspace, user_id=target_user_id).exists():
            return Response(
                {
                    "detail": "That user is not a member of this project's workspace.",
                    "code": "not_workspace_member",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        membership, created = ProjectMembership.objects.get_or_create(
            project=project, user_id=target_user_id, defaults={"added_by": request.user}
        )
        if not created:
            return Response(
                {"detail": "That user is already a project member.", "code": "already_member"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        log_activity(
            actor=request.user,
            event_type=ActivityEventType.PROJECT_MEMBER_ADDED,
            workspace=project.workspace,
            project=project,
            target_type="user",
            target_id=target_user_id,
        )
        return Response(ProjectMembershipSerializer(membership).data, status=status.HTTP_201_CREATED)


class ProjectMemberDetailView(APIView):
    permission_classes = PROJECT_PERMISSIONS

    def delete(self, request, project_id, user_id):
        project = _get_visible_project_or_404(request, project_id)
        if not can_manage_project(request.user, project):
            return Response(
                {"detail": "Only workspace owners and admins can remove project members.", "code": "forbidden"},
                status=status.HTTP_403_FORBIDDEN,
            )
        membership = get_object_or_404(ProjectMembership, project=project, user_id=user_id)
        log_activity(
            actor=request.user,
            event_type=ActivityEventType.PROJECT_MEMBER_REMOVED,
            workspace=project.workspace,
            project=project,
            target_type="user",
            target_id=user_id,
        )
        membership.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
