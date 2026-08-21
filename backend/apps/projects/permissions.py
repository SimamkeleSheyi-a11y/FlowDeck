from apps.workspaces.models import WorkspaceRole
from apps.workspaces.permissions import get_membership as get_workspace_membership

from .models import ProjectMembership


def get_workspace_role(user, workspace):
    membership = get_workspace_membership(user, workspace)
    return membership.role if membership else None


def has_project_access(user, project) -> bool:
    """
    OWNER/ADMIN: implicit access to every project in their workspace.
    MEMBER: only if they hold an explicit ProjectMembership on this project.
    Anyone with no workspace membership at all: no access.
    Phase 1 architecture doc, Section 6.1 — the single place this rule is
    encoded; every view goes through this (or visible_projects_for_user)
    rather than re-deriving it.
    """
    role = get_workspace_role(user, project.workspace)
    if role in (WorkspaceRole.OWNER, WorkspaceRole.ADMIN):
        return True
    if role == WorkspaceRole.MEMBER:
        return ProjectMembership.objects.filter(project=project, user=user).exists()
    return False


def can_manage_project(user, project) -> bool:
    """Create/edit/archive/delete a project and manage its membership list —
    OWNER/ADMIN only, regardless of explicit ProjectMembership."""
    return get_workspace_role(user, project.workspace) in (WorkspaceRole.OWNER, WorkspaceRole.ADMIN)
