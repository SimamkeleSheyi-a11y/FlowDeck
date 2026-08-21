from django.urls import path

from . import views

app_name = "boards"

urlpatterns = [
    path("boards/<uuid:board_id>/", views.BoardDetailView.as_view(), name="detail"),
    path("boards/<uuid:board_id>/full/", views.BoardFullView.as_view(), name="full"),
    path("boards/<uuid:board_id>/columns/", views.BoardColumnListCreateView.as_view(), name="columns"),
    path("columns/<uuid:column_id>/", views.BoardColumnDetailView.as_view(), name="column-detail"),
    path("columns/<uuid:column_id>/reorder/", views.BoardColumnReorderView.as_view(), name="column-reorder"),
]
