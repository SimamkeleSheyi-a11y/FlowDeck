from django.contrib import admin

from .models import ActivityEvent


@admin.register(ActivityEvent)
class ActivityEventAdmin(admin.ModelAdmin):
    list_display = ["event_type", "actor", "task", "project", "workspace", "created_at"]
    list_filter = ["event_type"]
    search_fields = ["task__title", "project__name", "workspace__name"]
    readonly_fields = ["id", "created_at"]
    ordering = ["-created_at"]
