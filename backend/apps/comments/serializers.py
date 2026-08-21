from rest_framework import serializers

from apps.users.serializers import UserSerializer

from .models import Comment


class CommentSerializer(serializers.ModelSerializer):
    task_id = serializers.UUIDField(source="task.id", read_only=True)
    author = UserSerializer(read_only=True)

    class Meta:
        model = Comment
        fields = ["id", "task_id", "author", "body", "created_at", "updated_at", "edited_at"]
        read_only_fields = fields


class CommentCreateSerializer(serializers.Serializer):
    body = serializers.CharField(max_length=4000)

    def validate_body(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Comment cannot be empty.")
        return value


class CommentUpdateSerializer(serializers.Serializer):
    body = serializers.CharField(max_length=4000)

    def validate_body(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Comment cannot be empty.")
        return value
