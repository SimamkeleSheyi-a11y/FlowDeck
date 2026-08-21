import uuid

from django.conf import settings
from django.db import models

from apps.tasks.models import Task


class Comment(models.Model):
    """
    Soft-delete (deleted_at) rather than a hard delete — Phase 1 doc,
    Section 5: "Comment supports soft-delete so activity history
    referencing a comment stays coherent" (a COMMENT_DELETED activity
    event can still make sense pointing at a target_id that still exists
    in the table, just hidden from normal reads).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+")
    body = models.TextField(max_length=4000)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    edited_at = models.DateTimeField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [models.Index(fields=["task", "created_at"], name="comments_c_task_created_idx")]

    def __str__(self):
        return f"Comment by {self.author_id} on {self.task_id}"
