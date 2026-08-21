from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    ordering = ["-created_at"]
    list_display = ["email", "display_name", "is_email_verified", "is_active", "is_staff", "created_at"]
    list_filter = ["is_email_verified", "is_active", "is_staff"]
    search_fields = ["email", "display_name"]
    readonly_fields = ["id", "created_at", "updated_at", "last_login"]

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Profile", {"fields": ("display_name", "bio", "avatar")}),
        (
            "Status",
            {"fields": ("is_email_verified", "is_active", "is_staff", "is_superuser", "groups", "user_permissions")},
        ),
        ("Important dates", {"fields": ("last_login", "created_at", "updated_at")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("email", "display_name", "password1", "password2")}),
    )
