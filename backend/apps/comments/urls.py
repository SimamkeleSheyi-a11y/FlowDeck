from django.urls import path

from . import views

app_name = "comments"

urlpatterns = [
    path("tasks/<uuid:task_id>/comments/", views.TaskCommentsView.as_view(), name="task-comments"),
    path("comments/<uuid:comment_id>/", views.CommentDetailView.as_view(), name="detail"),
]
