import re

from rest_framework import serializers

from apps.users.serializers import UserSerializer

from .models import Checklist, ChecklistItem, Label, Task, TaskAssignee, TaskPriority

HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


class LabelSerializer(serializers.ModelSerializer):
    class Meta:
        model = Label
        fields = ["id", "name", "color", "created_at"]
        read_only_fields = fields


class TaskAssigneeSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = TaskAssignee
        fields = ["id", "user", "assigned_at"]
        read_only_fields = fields


class TaskSerializer(serializers.ModelSerializer):
    column_id = serializers.UUIDField(source="column.id", read_only=True)
    project_id = serializers.UUIDField(source="project.id", read_only=True)
    created_by = UserSerializer(read_only=True)
    assignees = serializers.SerializerMethodField()
    labels = serializers.SerializerMethodField()
    checklist_total = serializers.SerializerMethodField()
    checklist_done = serializers.SerializerMethodField()

    class Meta:
        model = Task
        fields = [
            "id",
            "column_id",
            "project_id",
            "title",
            "description",
            "priority",
            "position",
            "start_date",
            "due_date",
            "is_completed",
            "version",
            "assignees",
            "labels",
            "checklist_total",
            "checklist_done",
            "created_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_assignees(self, obj):
        # obj.assignees.all() hits the prefetch cache when the view
        # prefetched it (list endpoint) and costs one small query otherwise
        # (single-object views) — correct and cheap either way.
        return TaskAssigneeSerializer(obj.assignees.all(), many=True).data

    def get_labels(self, obj):
        # Same reasoning as get_assignees — obj.task_labels.all() reads the
        # prefetch cache when present.
        return LabelSerializer([tl.label for tl in obj.task_labels.all()], many=True).data

    def get_checklist_total(self, obj):
        annotated = getattr(obj, "checklist_total_annotated", None)
        if annotated is not None:
            return annotated
        checklist = getattr(obj, "checklist", None)
        return checklist.items.count() if checklist else 0

    def get_checklist_done(self, obj):
        annotated = getattr(obj, "checklist_done_annotated", None)
        if annotated is not None:
            return annotated
        checklist = getattr(obj, "checklist", None)
        return checklist.items.filter(is_done=True).count() if checklist else 0


def _validate_date_order(attrs, instance=None):
    start = attrs.get("start_date", getattr(instance, "start_date", None))
    due = attrs.get("due_date", getattr(instance, "due_date", None))
    if start and due and start > due:
        raise serializers.ValidationError({"due_date": "Due date cannot be before the start date."})
    return attrs


class TaskCreateSerializer(serializers.Serializer):
    column_id = serializers.UUIDField()
    title = serializers.CharField(max_length=200)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    priority = serializers.ChoiceField(choices=TaskPriority.choices, required=False, default=TaskPriority.MEDIUM)
    start_date = serializers.DateField(required=False, allow_null=True, default=None)
    due_date = serializers.DateField(required=False, allow_null=True, default=None)

    def validate_title(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Task title cannot be empty.")
        return value

    def validate(self, attrs):
        return _validate_date_order(attrs)


class TaskUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = ["title", "description", "priority", "start_date", "due_date", "is_completed"]

    def validate_title(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Task title cannot be empty.")
        return value

    def validate(self, attrs):
        return _validate_date_order(attrs, instance=self.instance)


class TaskMoveSerializer(serializers.Serializer):
    column_id = serializers.UUIDField()
    after_task_id = serializers.UUIDField(required=False, allow_null=True, default=None)
    version = serializers.IntegerField(min_value=0)
    # Phase 8: opt-in strict conflict handling. Default False preserves the
    # Phase 5 accept-and-flag behavior exactly — every existing caller that
    # doesn't send this field is unaffected.
    strict = serializers.BooleanField(required=False, default=False)


class LabelCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=40)
    color = serializers.RegexField(regex=HEX_COLOR_RE, required=False, default="#6B7280")

    def validate_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Label name cannot be empty.")
        return value


class LabelUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Label
        fields = ["name", "color"]

    def validate_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Label name cannot be empty.")
        return value

    def validate_color(self, value):
        # Previously unvalidated on update — LabelCreateSerializer used a
        # RegexField for this, but LabelUpdateSerializer (a ModelSerializer)
        # just inherited the model field's bare CharField(max_length=7),
        # so a PATCH could set a non-hex value with no rejection at all.
        if not HEX_COLOR_RE.match(value):
            raise serializers.ValidationError("Color must be a hex code like #RRGGBB.")
        return value


class TaskAssignSerializer(serializers.Serializer):
    user_id = serializers.UUIDField()


class ChecklistItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChecklistItem
        fields = ["id", "text", "is_done", "position", "created_at"]
        read_only_fields = ["id", "position", "created_at"]


class ChecklistItemCreateSerializer(serializers.Serializer):
    text = serializers.CharField(max_length=280)

    def validate_text(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Checklist item text cannot be empty.")
        return value


class ChecklistItemUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChecklistItem
        fields = ["text", "is_done"]

    def validate_text(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Checklist item text cannot be empty.")
        return value


class ChecklistItemReorderSerializer(serializers.Serializer):
    after_item_id = serializers.UUIDField(required=False, allow_null=True, default=None)


class ChecklistSerializer(serializers.ModelSerializer):
    items = ChecklistItemSerializer(many=True, read_only=True)

    class Meta:
        model = Checklist
        fields = ["id", "items", "created_at"]
        read_only_fields = fields
