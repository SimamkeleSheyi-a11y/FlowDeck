"""
A task's access rules are exactly its project's — any project member (not
just OWNER/ADMIN) can create/edit/move/delete tasks, matching the original
spec's collaborative day-to-day-work model. Structural board changes
(columns) are the OWNER/ADMIN-only concern in apps.boards, not this.
"""
from apps.projects.permissions import has_project_access as has_project_access_


def has_task_access(user, task) -> bool:
    return has_project_access_(user, task.project)
