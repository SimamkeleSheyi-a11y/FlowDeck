from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("apps.users.urls")),
    path("api/", include("apps.workspaces.urls")),
    path("api/", include("apps.projects.urls")),
    path("api/", include("apps.boards.urls")),
    path("api/", include("apps.tasks.urls")),
    path("api/", include("apps.comments.urls")),
    path("api/", include("apps.activity.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
