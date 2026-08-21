from django.urls import path

from . import views

app_name = "tasks"

urlpatterns = [
    path("tasks/", views.TaskListCreateView.as_view(), name="list-create"),
    path("tasks/<uuid:task_id>/", views.TaskDetailView.as_view(), name="detail"),
    path("tasks/<uuid:task_id>/move/", views.TaskMoveView.as_view(), name="move"),
    path("tasks/<uuid:task_id>/assignees/", views.TaskAssigneesView.as_view(), name="assignees"),
    path(
        "tasks/<uuid:task_id>/assignees/<uuid:user_id>/",
        views.TaskAssigneeDetailView.as_view(),
        name="assignee-detail",
    ),
    path("tasks/<uuid:task_id>/labels/", views.TaskLabelsView.as_view(), name="task-labels"),
    path(
        "tasks/<uuid:task_id>/labels/<uuid:label_id>/",
        views.TaskLabelDetailView.as_view(),
        name="task-label-detail",
    ),
    path("tasks/<uuid:task_id>/checklist/", views.TaskChecklistView.as_view(), name="checklist"),
    path("checklist-items/<uuid:item_id>/", views.ChecklistItemDetailView.as_view(), name="checklist-item-detail"),
    path(
        "checklist-items/<uuid:item_id>/reorder/",
        views.ChecklistItemReorderView.as_view(),
        name="checklist-item-reorder",
    ),
    path("projects/<uuid:project_id>/labels/", views.LabelListCreateView.as_view(), name="project-labels"),
    path("labels/<uuid:label_id>/", views.LabelDetailView.as_view(), name="label-detail"),
]
