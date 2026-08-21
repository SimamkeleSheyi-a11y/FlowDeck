from django.contrib import admin

from .models import Board, BoardColumn


class BoardColumnInline(admin.TabularInline):
    model = BoardColumn
    extra = 0
    readonly_fields = ["id", "created_at"]
    ordering = ["position"]


@admin.register(Board)
class BoardAdmin(admin.ModelAdmin):
    list_display = ["project", "created_at"]
    search_fields = ["project__name"]
    readonly_fields = ["id", "created_at"]
    inlines = [BoardColumnInline]


@admin.register(BoardColumn)
class BoardColumnAdmin(admin.ModelAdmin):
    list_display = ["name", "board", "position", "created_at"]
    list_filter = ["board"]
    search_fields = ["name", "board__project__name"]
    readonly_fields = ["id", "created_at"]
    ordering = ["board", "position"]
