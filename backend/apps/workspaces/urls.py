from django.urls import path

from . import views

app_name = "workspaces"

urlpatterns = [
    path("workspaces/", views.WorkspaceListCreateView.as_view(), name="list-create"),
    path("workspaces/<uuid:workspace_id>/", views.WorkspaceDetailView.as_view(), name="detail"),
    path("workspaces/<uuid:workspace_id>/leave/", views.WorkspaceLeaveView.as_view(), name="leave"),
    path(
        "workspaces/<uuid:workspace_id>/ownership/transfer/",
        views.OwnershipTransferView.as_view(),
        name="ownership-transfer",
    ),
    path("workspaces/<uuid:workspace_id>/members/", views.WorkspaceMembersView.as_view(), name="members"),
    path(
        "workspaces/<uuid:workspace_id>/members/<uuid:user_id>/",
        views.WorkspaceMemberDetailView.as_view(),
        name="member-detail",
    ),
    path(
        "workspaces/<uuid:workspace_id>/invitations/",
        views.WorkspaceInvitationListCreateView.as_view(),
        name="invitations",
    ),
    path(
        "workspaces/<uuid:workspace_id>/invitations/<uuid:invitation_id>/",
        views.WorkspaceInvitationRevokeView.as_view(),
        name="invitation-revoke",
    ),
    path("invitations/<str:token>/", views.InvitationPreviewView.as_view(), name="invitation-preview"),
    path("invitations/<str:token>/accept/", views.InvitationAcceptView.as_view(), name="invitation-accept"),
]
