from django.contrib import admin

from .models import Profile


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("name", "display_name", "language", "mail_source", "enabled")
    list_filter = ("enabled", "language")
    search_fields = ("name", "display_name")
