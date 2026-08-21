"""
A board/column's access rules are exactly its project's — there's no
separate board-level role. Thin wrappers around apps.projects.permissions
so callers don't need to know that.
"""
from apps.projects.permissions import can_manage_project as can_manage_project_
from apps.projects.permissions import has_project_access as has_project_access_


def has_board_access(user, board) -> bool:
    return has_project_access_(user, board.project)


def can_manage_board(user, board) -> bool:
    """Create/rename/delete/reorder columns — structural board changes are
    an OWNER/ADMIN concern, same as project management. Working with tasks
    themselves (Phase 5's Task views) is open to any project member."""
    return can_manage_project_(user, board.project)
