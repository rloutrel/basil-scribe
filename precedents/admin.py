from django.contrib import admin

from .models import ArchiveMail, ExtractionReport, Precedent


@admin.register(ArchiveMail)
class ArchiveMailAdmin(admin.ModelAdmin):
    list_display = ("profile", "subject", "sender", "date", "is_outgoing")
    list_filter = ("profile", "is_outgoing")
    search_fields = ("subject", "sender", "body")


@admin.register(Precedent)
class PrecedentAdmin(admin.ModelAdmin):
    list_display = (
        "profile",
        "request_type",
        "answer_category",
        "match_source",
        "match_type",
    )
    list_filter = ("profile", "request_type", "match_type")


@admin.register(ExtractionReport)
class ExtractionReportAdmin(admin.ModelAdmin):
    list_display = ("profile", "created_at", "mails_parsed", "pairs_matched")
    list_filter = ("profile",)
