from django.contrib import admin

from .models import Comment


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ["task", "author", "created_at", "edited_at", "deleted_at"]
    list_filter = ["deleted_at"]
    search_fields = ["task__title", "author__email", "body"]
    readonly_fields = ["id", "created_at", "updated_at"]
    ordering = ["-created_at"]
