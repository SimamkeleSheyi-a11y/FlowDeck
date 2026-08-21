from apps.projects.selectors import visible_projects_for_user

from .models import Task


def visible_tasks_for_user(user):
    return Task.objects.filter(project__in=visible_projects_for_user(user))
