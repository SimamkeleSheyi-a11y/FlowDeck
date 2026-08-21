from rest_framework import serializers

from apps.users.serializers import UserSerializer

from .models import (
    InvitationRole,
    InvitationStatus,
    Workspace,
    WorkspaceInvitation,
    WorkspaceMembership,
    WorkspaceRole,
)


class WorkspaceSerializer(serializers.ModelSerializer):
    my_role = serializers.SerializerMethodField()

    class Meta:
        model = Workspace
        fields = ["id", "name", "slug", "description", "created_at", "updated_at", "archived_at", "my_role"]
        read_only_fields = ["id", "slug", "created_at", "updated_at", "archived_at", "my_role"]

    def get_my_role(self, obj):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return None
        prefetched = getattr(obj, "my_memberships", None)
        if prefetched is not None:
            # Populated by WorkspaceListCreateView via Prefetch(to_attr=...)
            # — zero extra queries per workspace in a list response.
            return prefetched[0].role if prefetched else None
        # Single-object views (e.g. WorkspaceDetailView) don't prefetch —
        # one query here is fine, it's not repeated per-object in a list.
        membership = obj.memberships.filter(user=request.user).first()
        return membership.role if membership else None


class WorkspaceCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Workspace
        fields = ["name", "description"]

    def validate_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Workspace name cannot be empty.")
        return value


class WorkspaceUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Workspace
        fields = ["name", "description"]

    def validate_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Workspace name cannot be empty.")
        return value


class WorkspaceMembershipSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = WorkspaceMembership
        fields = ["id", "user", "role", "joined_at"]
        read_only_fields = fields


class MembershipRoleUpdateSerializer(serializers.Serializer):
    # OWNER is deliberately not a valid choice here — ownership only moves
    # via OwnershipTransferView, never a generic role PATCH.
    role = serializers.ChoiceField(choices=[WorkspaceRole.ADMIN, WorkspaceRole.MEMBER])


class OwnershipTransferSerializer(serializers.Serializer):
    user_id = serializers.UUIDField()


class WorkspaceInvitationSerializer(serializers.ModelSerializer):
    invited_by = UserSerializer(read_only=True)

    class Meta:
        model = WorkspaceInvitation
        fields = ["id", "email", "invited_by", "intended_role", "status", "expires_at", "created_at", "responded_at"]
        read_only_fields = fields


class WorkspaceInvitationCreateSerializer(serializers.Serializer):
    email = serializers.EmailField()
    intended_role = serializers.ChoiceField(
        choices=[InvitationRole.ADMIN, InvitationRole.MEMBER], default=InvitationRole.MEMBER
    )

    def validate_email(self, value):
        return value.strip().lower()


class InvitationPreviewSerializer(serializers.ModelSerializer):
    workspace_name = serializers.CharField(source="workspace.name", read_only=True)
    invited_by_name = serializers.SerializerMethodField()
    is_valid = serializers.SerializerMethodField()

    class Meta:
        model = WorkspaceInvitation
        fields = ["workspace_name", "invited_by_name", "intended_role", "status", "expires_at", "is_valid"]
        read_only_fields = fields

    def get_invited_by_name(self, obj):
        return obj.invited_by.display_name if obj.invited_by else None

    def get_is_valid(self, obj):
        return obj.status == InvitationStatus.PENDING and not obj.is_expired
