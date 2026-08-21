from apps.projects.selectors import visible_projects_for_user

from .models import Board


def visible_boards_for_user(user):
    """A board is visible exactly when its project is (Section 6.1) — one
    board per project, so this just follows the project's visibility."""
    return Board.objects.filter(project__in=visible_projects_for_user(user))
