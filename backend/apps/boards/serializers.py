from rest_framework import serializers

from .models import Board, BoardColumn


class BoardColumnSerializer(serializers.ModelSerializer):
    class Meta:
        model = BoardColumn
        fields = ["id", "name", "position", "created_at"]
        read_only_fields = fields


class BoardSerializer(serializers.ModelSerializer):
    project_id = serializers.UUIDField(source="project.id", read_only=True)
    columns = BoardColumnSerializer(many=True, read_only=True)

    class Meta:
        model = Board
        fields = ["id", "project_id", "columns", "created_at"]
        read_only_fields = fields


class BoardColumnWithTasksSerializer(serializers.ModelSerializer):
    """
    Phase 8 — same shape as BoardColumnSerializer plus a nested `tasks`
    list, used only by the full board endpoint
    (GET /api/boards/{id}/full/). Kept as a separate serializer rather than
    adding `tasks` to BoardColumnSerializer itself, so the existing
    GET/POST /api/boards/{id}/columns/ responses are completely unchanged.
    """

    tasks = serializers.SerializerMethodField()

    class Meta:
        model = BoardColumn
        fields = ["id", "name", "position", "created_at", "tasks"]
        read_only_fields = fields

    def get_tasks(self, obj):
        # Local import: avoids any top-level apps.boards <-> apps.tasks
        # import-order assumption (apps.tasks.models already imports
        # apps.boards.models for the Task.column FK) — deferred until
        # actually called, well after all apps are loaded.
        from apps.tasks.serializers import TaskSerializer

        return TaskSerializer(obj.tasks.all(), many=True).data


class BoardWithTasksSerializer(serializers.ModelSerializer):
    """Phase 8 — full board state: columns in position order, each with its
    tasks in position order. See BoardFullView for the N+1-safe queryset
    this is paired with."""

    project_id = serializers.UUIDField(source="project.id", read_only=True)
    columns = BoardColumnWithTasksSerializer(many=True, read_only=True)

    class Meta:
        model = Board
        fields = ["id", "project_id", "columns", "created_at"]
        read_only_fields = fields


class BoardColumnCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=50)

    def validate_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Column name cannot be empty.")
        return value


class BoardColumnUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = BoardColumn
        fields = ["name"]

    def validate_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Column name cannot be empty.")
        return value


class BoardColumnReorderSerializer(serializers.Serializer):
    after_column_id = serializers.UUIDField(required=False, allow_null=True, default=None)
