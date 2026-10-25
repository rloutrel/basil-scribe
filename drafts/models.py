from django.db import models
from django.utils.translation import gettext_lazy as _

STATUS_CHOICES = [
    ("generated", _("Generated")),
    ("accepted", _("Accepted")),
]


class Draft(models.Model):
    """A generated reply draft, its final human-reviewed version and the
    precedents that inspired it. Never sent automatically."""

    profile = models.ForeignKey(
        "profiles.Profile",
        verbose_name=_("Profile"),
        on_delete=models.CASCADE,
        related_name="drafts",
    )
    request_type = models.CharField(_("Request type"), max_length=120)
    request_text = models.TextField(_("Request text"))
    recipient_name = models.CharField(
        _("Recipient name"), max_length=255, blank=True, default=""
    )
    request_date = models.CharField(
        _("Request date"), max_length=64, blank=True, default=""
    )
    generated_text = models.TextField(_("LLM draft"), blank=True, default="")
    final_text = models.TextField(_("Final version"), blank=True, default="")
    precedents_used = models.JSONField(
        _("Precedents used"), default=list, blank=True
    )
    status = models.CharField(
        _("Status"), max_length=20, choices=STATUS_CHOICES, default="generated"
    )
    added_as_precedent = models.BooleanField(_("Added as precedent"), default=False)
    created_at = models.DateTimeField(_("Created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated at"), auto_now=True)

    class Meta:
        verbose_name = _("Draft")
        verbose_name_plural = _("Drafts")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.profile.name} / {self.request_type} / {self.pk}"
