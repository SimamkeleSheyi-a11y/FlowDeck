from django.urls import path

from . import views

app_name = "projects"

urlpatterns = [
    path("projects/", views.ProjectListCreateView.as_view(), name="list-create"),
    path("projects/<uuid:project_id>/", views.ProjectDetailView.as_view(), name="detail"),
    path("projects/<uuid:project_id>/archive/", views.ProjectArchiveView.as_view(), name="archive"),
    path("projects/<uuid:project_id>/unarchive/", views.ProjectUnarchiveView.as_view(), name="unarchive"),
    path("projects/<uuid:project_id>/members/", views.ProjectMembersView.as_view(), name="members"),
    path(
        "projects/<uuid:project_id>/members/<uuid:user_id>/",
        views.ProjectMemberDetailView.as_view(),
        name="member-detail",
    ),
]
