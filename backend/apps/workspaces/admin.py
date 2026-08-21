from django.contrib import admin

from .models import Workspace, WorkspaceInvitation, WorkspaceMembership


class WorkspaceMembershipInline(admin.TabularInline):
    model = WorkspaceMembership
    extra = 0
    readonly_fields = ["id", "joined_at"]


@admin.register(Workspace)
class WorkspaceAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "created_by", "created_at", "archived_at"]
    search_fields = ["name", "slug"]
    list_filter = ["archived_at"]
    readonly_fields = ["id", "slug", "created_at", "updated_at"]
    ordering = ["-created_at"]
    inlines = [WorkspaceMembershipInline]


@admin.register(WorkspaceMembership)
class WorkspaceMembershipAdmin(admin.ModelAdmin):
    list_display = ["workspace", "user", "role", "joined_at"]
    list_filter = ["role"]
    search_fields = ["workspace__name", "user__email"]
    readonly_fields = ["id", "joined_at"]
    ordering = ["-joined_at"]


@admin.register(WorkspaceInvitation)
class WorkspaceInvitationAdmin(admin.ModelAdmin):
    list_display = ["email", "workspace", "intended_role", "status", "invited_by", "expires_at", "created_at"]
    list_filter = ["status", "intended_role"]
    search_fields = ["email", "workspace__name"]
    readonly_fields = ["id", "token_hash", "created_at", "responded_at"]
    ordering = ["-created_at"]
