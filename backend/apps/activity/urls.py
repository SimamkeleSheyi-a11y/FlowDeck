from django.urls import path

from . import views

app_name = "activity"

urlpatterns = [
    path("tasks/<uuid:task_id>/activity/", views.TaskActivityView.as_view(), name="task-activity"),
]
