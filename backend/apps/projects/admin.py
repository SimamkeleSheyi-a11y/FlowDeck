from django.contrib import admin

from .models import Project, ProjectMembership


class ProjectMembershipInline(admin.TabularInline):
    model = ProjectMembership
    extra = 0
    readonly_fields = ["id", "joined_at"]


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ["name", "workspace", "created_by", "created_at", "archived_at"]
    list_filter = ["archived_at", "workspace"]
    search_fields = ["name", "workspace__name"]
    readonly_fields = ["id", "created_at", "updated_at"]
    ordering = ["-created_at"]
    inlines = [ProjectMembershipInline]


@admin.register(ProjectMembership)
class ProjectMembershipAdmin(admin.ModelAdmin):
    list_display = ["project", "user", "added_by", "joined_at"]
    search_fields = ["project__name", "user__email"]
    readonly_fields = ["id", "joined_at"]
    ordering = ["-joined_at"]
