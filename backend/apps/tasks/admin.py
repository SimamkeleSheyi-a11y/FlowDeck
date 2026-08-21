from django.contrib import admin

from .models import Checklist, ChecklistItem, Label, Task, TaskAssignee, TaskLabel


class TaskAssigneeInline(admin.TabularInline):
    model = TaskAssignee
    extra = 0
    readonly_fields = ["id", "assigned_at"]


class TaskLabelInline(admin.TabularInline):
    model = TaskLabel
    extra = 0
    readonly_fields = ["id", "added_at"]


class ChecklistItemInline(admin.TabularInline):
    model = ChecklistItem
    extra = 0
    readonly_fields = ["id", "created_at"]
    ordering = ["position"]


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ["title", "project", "column", "priority", "is_completed", "due_date", "created_by", "created_at"]
    list_filter = ["priority", "is_completed", "project"]
    search_fields = ["title", "project__name"]
    readonly_fields = ["id", "version", "created_at", "updated_at"]
    ordering = ["-created_at"]
    inlines = [TaskAssigneeInline, TaskLabelInline]


@admin.register(Label)
class LabelAdmin(admin.ModelAdmin):
    list_display = ["name", "color", "project", "created_at"]
    list_filter = ["project"]
    search_fields = ["name", "project__name"]
    readonly_fields = ["id", "created_at"]


@admin.register(Checklist)
class ChecklistAdmin(admin.ModelAdmin):
    list_display = ["task", "created_at"]
    search_fields = ["task__title"]
    readonly_fields = ["id", "created_at"]
    inlines = [ChecklistItemInline]
