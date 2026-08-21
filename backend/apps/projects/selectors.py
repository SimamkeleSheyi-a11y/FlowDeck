"""
Query-building helpers kept separate from views.py so the "what can this
user even see" logic lives in exactly one place.
"""
from django.db.models import Q

from apps.workspaces.models import WorkspaceMembership, WorkspaceRole

from .models import Project, ProjectMembership


def visible_projects_for_user(user):
    """
    A project is visible to a user if either:
      - they're OWNER or ADMIN of the project's workspace (implicit access,
        Section 6.1), or
      - they hold an explicit ProjectMembership on that exact project.

    Used for both the project list endpoint and IDOR-safe single-object
    lookups — a project outside this set is treated as not existing (404),
    not as existing-but-forbidden (403), same policy as workspaces.
    """
    owner_admin_workspace_ids = WorkspaceMembership.objects.filter(
        user=user, role__in=[WorkspaceRole.OWNER, WorkspaceRole.ADMIN]
    ).values_list("workspace_id", flat=True)

    member_project_ids = ProjectMembership.objects.filter(user=user).values_list("project_id", flat=True)

    return Project.objects.filter(
        Q(workspace_id__in=owner_admin_workspace_ids) | Q(id__in=member_project_ids)
    ).distinct()
