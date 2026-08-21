"""A comment's access rules are exactly its task's project's — any project
member can comment (matches task-editing openness, Phase 5/6 precedent).
Editing/deleting is further restricted to the comment's own author only —
"edit their own comments / delete their own comments" from the original
spec; not even OWNER/ADMIN can touch someone else's comment here."""
from apps.projects.permissions import has_project_access as has_project_access_


def has_comment_thread_access(user, task) -> bool:
    return has_project_access_(user, task.project)


def can_modify_comment(user, comment) -> bool:
    return comment.author_id == user.id
