from rest_framework import serializers

from apps.users.serializers import UserSerializer

from .models import ActivityEvent


class ActivityEventSerializer(serializers.ModelSerializer):
    actor = UserSerializer(read_only=True)

    class Meta:
        model = ActivityEvent
        fields = [
            "id",
            "actor",
            "event_type",
            "target_type",
            "target_id",
            "metadata",
            "created_at",
        ]
        read_only_fields = fields
