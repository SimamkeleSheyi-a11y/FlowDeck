from django.db import connection, transaction
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.activity.models import ActivityEventType
from apps.activity.services import log_activity
from apps.users.permissions import IsEmailVerified

from .models import (
    InvitationRole,
    InvitationStatus,
    Workspace,
    WorkspaceInvitation,
    WorkspaceMembership,
    WorkspaceRole,
)
from .permissions import get_membership
from .serializers import (
    InvitationPreviewSerializer,
    MembershipRoleUpdateSerializer,
    OwnershipTransferSerializer,
    WorkspaceCreateSerializer,
    WorkspaceInvitationCreateSerializer,
    WorkspaceInvitationSerializer,
    WorkspaceMembershipSerializer,
    WorkspaceSerializer,
    WorkspaceUpdateSerializer,
)
from .services import (
    accept_invitation,
    create_invitation,
    expire_stale_invitations,
    resolve_invitation_by_raw_token,
    revoke_invitation,
)

# "Workspace functionality" (per the Phase 3 correction) requires a verified
# email across the board — every authenticated view below adds
# IsEmailVerified alongside IsAuthenticated. The one exception is the public,
# unauthenticated invitation preview, which has no user/session to verify.
WORKSPACE_PERMISSIONS = [IsAuthenticated, IsEmailVerified]


def _get_user_workspace_or_404(request, workspace_id):
    """
    Scoped by membership, never by raw PK alone — a non-member's request for
    a real workspace ID gets a plain 404, the same as a nonexistent ID would.
    That's deliberate: it keeps a workspace's very existence invisible to
    outsiders, not just its contents. (Phase 1 architecture doc, Section 11.)
    """
    return get_object_or_404(
        Workspace.objects.filter(memberships__user=request.user).distinct(),
        id=workspace_id,
    )


class WorkspaceListCreateView(APIView):
    permission_classes = WORKSPACE_PERMISSIONS
    pagination_class = LimitOffsetPagination

    def get(self, request):
        # Attach only *this user's* membership row per workspace via
        # Prefetch(to_attr=...) so WorkspaceSerializer.get_my_role reads it
        # from memory instead of issuing one query per workspace in the
        # page (the N+1 this replaces).
        my_membership_qs = WorkspaceMembership.objects.filter(user=request.user)
        workspaces = (
            Workspace.objects.filter(memberships__user=request.user)
            .distinct()
            .prefetch_related(Prefetch("memberships", queryset=my_membership_qs, to_attr="my_memberships"))
            .order_by("-created_at")
        )

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(workspaces, request, view=self)
        serializer = WorkspaceSerializer(page, many=True, context={"request": request})
        return paginator.get_paginated_response(serializer.data)

    def post(self, request):
        serializer = WorkspaceCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            workspace = Workspace.objects.create(created_by=request.user, **serializer.validated_data)
            WorkspaceMembership.objects.create(workspace=workspace, user=request.user, role=WorkspaceRole.OWNER)
        log_activity(actor=request.user, event_type=ActivityEventType.WORKSPACE_CREATED, workspace=workspace)
        return Response(
            WorkspaceSerializer(workspace, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class WorkspaceDetailView(APIView):
    permission_classes = WORKSPACE_PERMISSIONS

    def get(self, request, workspace_id):
        workspace = _get_user_workspace_or_404(request, workspace_id)
        return Response(WorkspaceSerializer(workspace, context={"request": request}).data)

    def patch(self, request, workspace_id):
        workspace = _get_user_workspace_or_404(request, workspace_id)
        membership = get_membership(request.user, workspace)
        if membership.role not in (WorkspaceRole.OWNER, WorkspaceRole.ADMIN):
            return Response(
                {"detail": "Only workspace owners and admins can edit workspace settings.", "code": "forbidden"},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = WorkspaceUpdateSerializer(workspace, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(WorkspaceSerializer(workspace, context={"request": request}).data)

    def delete(self, request, workspace_id):
        workspace = _get_user_workspace_or_404(request, workspace_id)
        membership = get_membership(request.user, workspace)
        if membership.role != WorkspaceRole.OWNER:
            return Response(
                {"detail": "Only the workspace owner can delete the workspace.", "code": "forbidden"},
                status=status.HTTP_403_FORBIDDEN,
            )
        workspace.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class WorkspaceLeaveView(APIView):
    permission_classes = WORKSPACE_PERMISSIONS

    def post(self, request, workspace_id):
        workspace = _get_user_workspace_or_404(request, workspace_id)
        membership = get_membership(request.user, workspace)
        if membership.role == WorkspaceRole.OWNER:
            return Response(
                {
                    "detail": "Transfer ownership before leaving a workspace you own.",
                    "code": "owner_must_transfer_first",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        membership.delete()
        log_activity(
            actor=request.user,
            event_type=ActivityEventType.WORKSPACE_MEMBER_REMOVED,
            workspace=workspace,
            target_type="user",
            target_id=request.user.id,
            metadata={"self_initiated": True},
        )
        return Response({"detail": "You have left the workspace.", "code": "left_workspace"})


class OwnershipTransferView(APIView):
    permission_classes = WORKSPACE_PERMISSIONS

    def post(self, request, workspace_id):
        workspace = _get_user_workspace_or_404(request, workspace_id)
        membership = get_membership(request.user, workspace)
        if membership is None or membership.role != WorkspaceRole.OWNER:
            return Response(
                {"detail": "Only the current owner can transfer ownership.", "code": "forbidden"},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = OwnershipTransferSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        target_user_id = serializer.validated_data["user_id"]

        if str(target_user_id) == str(request.user.id):
            return Response(
                {"detail": "You already own this workspace.", "code": "already_owner"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            owner_qs = WorkspaceMembership.objects.filter(workspace=workspace, role=WorkspaceRole.OWNER)
            target_qs = WorkspaceMembership.objects.filter(workspace=workspace, user_id=target_user_id)

            # Row-level locking is a Postgres/production feature; SQLite
            # (used for quick local/dev runs) doesn't support SELECT ... FOR
            # UPDATE at all, so this only locks where the backend actually
            # supports it. The re-check immediately below still runs either
            # way — on SQLite it protects against the case being tested
            # (stale precondition), just not against genuine concurrent
            # transactions the way Postgres's real row lock does.
            if connection.features.has_select_for_update:
                owner_qs = owner_qs.select_for_update()
                target_qs = target_qs.select_for_update()

            current_owner_membership = owner_qs.first()
            target_membership = target_qs.first()

            # Re-check everything *after* the lock: state may have moved
            # between the optimistic permission check above and here — e.g.
            # a concurrent transfer already completed, or the target left
            # the workspace in the meantime.
            if current_owner_membership is None or current_owner_membership.user_id != request.user.id:
                return Response(
                    {
                        "detail": "Ownership already changed since you loaded this page — refresh and try again.",
                        "code": "ownership_changed",
                    },
                    status=status.HTTP_409_CONFLICT,
                )
            if target_membership is None:
                return Response(
                    {"detail": "That user is not a member of this workspace.", "code": "not_a_member"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if target_membership.role == WorkspaceRole.OWNER:
                return Response(
                    {"detail": "You already own this workspace.", "code": "already_owner"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            current_owner_membership.role = WorkspaceRole.ADMIN
            current_owner_membership.save(update_fields=["role"])
            target_membership.role = WorkspaceRole.OWNER
            target_membership.save(update_fields=["role"])

        log_activity(
            actor=request.user,
            event_type=ActivityEventType.WORKSPACE_OWNERSHIP_TRANSFERRED,
            workspace=workspace,
            target_type="user",
            target_id=target_membership.user_id,
            metadata={"previous_owner_id": str(request.user.id)},
        )
        return Response(WorkspaceSerializer(workspace, context={"request": request}).data)


class WorkspaceMembersView(APIView):
    permission_classes = WORKSPACE_PERMISSIONS

    def get(self, request, workspace_id):
        workspace = _get_user_workspace_or_404(request, workspace_id)
        memberships = workspace.memberships.select_related("user").order_by("role", "joined_at")
        return Response(WorkspaceMembershipSerializer(memberships, many=True).data)


class WorkspaceMemberDetailView(APIView):
    permission_classes = WORKSPACE_PERMISSIONS

    def patch(self, request, workspace_id, user_id):
        workspace = _get_user_workspace_or_404(request, workspace_id)
        requester_membership = get_membership(request.user, workspace)
        if requester_membership.role != WorkspaceRole.OWNER:
            return Response(
                {"detail": "Only the workspace owner can change member roles.", "code": "forbidden"},
                status=status.HTTP_403_FORBIDDEN,
            )

        target = get_object_or_404(WorkspaceMembership, workspace=workspace, user_id=user_id)
        if target.role == WorkspaceRole.OWNER:
            return Response(
                {
                    "detail": "Use the ownership-transfer endpoint to change the owner.",
                    "code": "use_transfer_endpoint",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = MembershipRoleUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        old_role = target.role
        target.role = serializer.validated_data["role"]
        target.save(update_fields=["role"])
        log_activity(
            actor=request.user,
            event_type=ActivityEventType.WORKSPACE_MEMBER_ROLE_CHANGED,
            workspace=workspace,
            target_type="user",
            target_id=target.user_id,
            metadata={"from": old_role, "to": target.role},
        )
        return Response(WorkspaceMembershipSerializer(target).data)

    def delete(self, request, workspace_id, user_id):
        workspace = _get_user_workspace_or_404(request, workspace_id)
        requester_membership = get_membership(request.user, workspace)
        if requester_membership.role not in (WorkspaceRole.OWNER, WorkspaceRole.ADMIN):
            return Response(
                {"detail": "Only workspace owners and admins can remove members.", "code": "forbidden"},
                status=status.HTTP_403_FORBIDDEN,
            )

        if str(user_id) == str(request.user.id):
            return Response(
                {"detail": "Use the leave-workspace endpoint to remove yourself.", "code": "use_leave_endpoint"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        target = get_object_or_404(WorkspaceMembership, workspace=workspace, user_id=user_id)
        if target.role == WorkspaceRole.OWNER:
            return Response(
                {"detail": "The workspace owner cannot be removed.", "code": "cannot_remove_owner"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if target.role == WorkspaceRole.ADMIN and requester_membership.role != WorkspaceRole.OWNER:
            # Same "only OWNER manages admins" principle already used for
            # invitations (an ADMIN can invite/manage MEMBERs but not peer
            # ADMINs) — applied to removal too, not just invites/role changes.
            return Response(
                {"detail": "Only the workspace owner can remove an admin.", "code": "only_owner_can_remove_admin"},
                status=status.HTTP_403_FORBIDDEN,
            )

        target.delete()
        log_activity(
            actor=request.user,
            event_type=ActivityEventType.WORKSPACE_MEMBER_REMOVED,
            workspace=workspace,
            target_type="user",
            target_id=user_id,
            metadata={"self_initiated": False},
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class WorkspaceInvitationListCreateView(APIView):
    permission_classes = WORKSPACE_PERMISSIONS

    def get(self, request, workspace_id):
        workspace = _get_user_workspace_or_404(request, workspace_id)
        membership = get_membership(request.user, workspace)
        if membership.role not in (WorkspaceRole.OWNER, WorkspaceRole.ADMIN):
            return Response(
                {"detail": "Only workspace owners and admins can view invitations.", "code": "forbidden"},
                status=status.HTTP_403_FORBIDDEN,
            )
        expire_stale_invitations(workspace)
        invitations = workspace.invitations.filter(status=InvitationStatus.PENDING).select_related("invited_by")
        return Response(WorkspaceInvitationSerializer(invitations, many=True).data)

    def post(self, request, workspace_id):
        workspace = _get_user_workspace_or_404(request, workspace_id)
        membership = get_membership(request.user, workspace)
        if membership.role not in (WorkspaceRole.OWNER, WorkspaceRole.ADMIN):
            return Response(
                {"detail": "Only workspace owners and admins can send invitations.", "code": "forbidden"},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = WorkspaceInvitationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]
        intended_role = serializer.validated_data["intended_role"]

        # Only the OWNER manages admins — an ADMIN may invite MEMBERs but
        # not other ADMINs. (Phase 3 correction.)
        if intended_role == InvitationRole.ADMIN and membership.role != WorkspaceRole.OWNER:
            return Response(
                {
                    "detail": "Only the workspace owner can invite someone as an admin.",
                    "code": "only_owner_can_invite_admin",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        if WorkspaceMembership.objects.filter(workspace=workspace, user__email__iexact=email).exists():
            return Response(
                {"detail": "That person is already a member of this workspace.", "code": "already_member"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Sweep first: an invitation that expired weeks ago must not block a
        # fresh invite to the same email just because its status column
        # never got updated off PENDING. (Phase 3 correction.)
        expire_stale_invitations(workspace)
        if workspace.invitations.filter(email__iexact=email, status=InvitationStatus.PENDING).exists():
            return Response(
                {"detail": "There's already a pending invitation for that email.", "code": "invitation_pending"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        invitation = create_invitation(workspace, email, request.user, intended_role)
        return Response(WorkspaceInvitationSerializer(invitation).data, status=status.HTTP_201_CREATED)


class WorkspaceInvitationRevokeView(APIView):
    permission_classes = WORKSPACE_PERMISSIONS

    def delete(self, request, workspace_id, invitation_id):
        workspace = _get_user_workspace_or_404(request, workspace_id)
        membership = get_membership(request.user, workspace)
        if membership.role not in (WorkspaceRole.OWNER, WorkspaceRole.ADMIN):
            return Response(
                {"detail": "Only workspace owners and admins can revoke invitations.", "code": "forbidden"},
                status=status.HTTP_403_FORBIDDEN,
            )
        invitation = get_object_or_404(WorkspaceInvitation, workspace=workspace, id=invitation_id)
        if invitation.status != InvitationStatus.PENDING:
            return Response(
                {"detail": "Only a pending invitation can be revoked.", "code": "not_pending"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if invitation.intended_role == InvitationRole.ADMIN and membership.role != WorkspaceRole.OWNER:
            # Symmetric with the send-side rule: an ADMIN can send/manage
            # MEMBER-role invitations but not ADMIN-role ones, so they can't
            # revoke one either.
            return Response(
                {
                    "detail": "Only the workspace owner can revoke an admin invitation.",
                    "code": "only_owner_can_revoke_admin_invitation",
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        revoke_invitation(invitation)
        return Response(status=status.HTTP_204_NO_CONTENT)


class InvitationPreviewView(APIView):
    """Public (unauthenticated) so someone can see what they're being invited
    to before deciding to register/log in. Deliberately NOT gated by
    IsEmailVerified — there's no authenticated user at all at this point."""

    permission_classes = [AllowAny]

    def get(self, request, token):
        invitation = resolve_invitation_by_raw_token(token)
        if not invitation:
            return Response(
                {"detail": "This invitation link is invalid or has expired.", "code": "invalid_invitation"},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(InvitationPreviewSerializer(invitation).data)


class InvitationAcceptView(APIView):
    permission_classes = WORKSPACE_PERMISSIONS

    def post(self, request, token):
        invitation = resolve_invitation_by_raw_token(token)
        if not invitation:
            return Response(
                {"detail": "This invitation link is invalid or has expired.", "code": "invalid_invitation"},
                status=status.HTTP_404_NOT_FOUND,
            )
        if invitation.email.lower() != request.user.email.lower():
            return Response(
                {"detail": "This invitation was sent to a different email address.", "code": "email_mismatch"},
                status=status.HTTP_403_FORBIDDEN,
            )
        accept_invitation(invitation, request.user)
        log_activity(
            actor=request.user,
            event_type=ActivityEventType.WORKSPACE_MEMBER_JOINED,
            workspace=invitation.workspace,
            target_type="user",
            target_id=request.user.id,
            metadata={"role": invitation.intended_role, "via": "invitation"},
        )
        return Response(WorkspaceSerializer(invitation.workspace, context={"request": request}).data)
