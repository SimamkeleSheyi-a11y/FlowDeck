from rest_framework import serializers

from apps.users.serializers import UserSerializer

from .models import Project, ProjectMembership


class ProjectSerializer(serializers.ModelSerializer):
    workspace_id = serializers.UUIDField(source="workspace.id", read_only=True)
    workspace_name = serializers.CharField(source="workspace.name", read_only=True)
    board_id = serializers.SerializerMethodField()
    am_i_a_project_member = serializers.SerializerMethodField()

    class Meta:
        model = Project
        fields = [
            "id",
            "workspace_id",
            "workspace_name",
            "board_id",
            "name",
            "description",
            "created_at",
            "updated_at",
            "archived_at",
            "am_i_a_project_member",
        ]
        read_only_fields = fields

    def get_board_id(self, obj):
        # Every project gets a board automatically on creation (see
        # apps.boards.services.create_default_board, called from
        # ProjectListCreateView.post) — the hasattr guard is defensive only,
        # in case that invariant is ever violated by data created another way.
        board = getattr(obj, "board", None)
        return board.id if board else None

    def get_am_i_a_project_member(self, obj):
        """
        Distinguishes "I can see this as a workspace OWNER/ADMIN" from "I'm
        actually on the project team" — OWNER/ADMIN can see every project
        in their workspace (Section 6.1) whether or not they're explicitly
        added, so this tells the frontend which case it's looking at.
        """
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False
        prefetched = getattr(obj, "my_memberships", None)
        if prefetched is not None:
            return bool(prefetched)
        return obj.memberships.filter(user=request.user).exists()


class ProjectCreateSerializer(serializers.Serializer):
    workspace_id = serializers.UUIDField()
    name = serializers.CharField(max_length=100)
    description = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")

    def validate_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Project name cannot be empty.")
        return value


class ProjectUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = ["name", "description"]

    def validate_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Project name cannot be empty.")
        return value


class ProjectMembershipSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = ProjectMembership
        fields = ["id", "user", "joined_at"]
        read_only_fields = fields


class ProjectMemberAddSerializer(serializers.Serializer):
    user_id = serializers.UUIDField()
