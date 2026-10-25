from django.contrib import admin

from .models import Draft


@admin.register(Draft)
class DraftAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "profile",
        "request_type",
        "created_at",
        "added_as_precedent",
    )
    list_filter = ("profile", "request_type", "added_as_precedent")
    search_fields = ("request_text", "generated_text", "final_text")
