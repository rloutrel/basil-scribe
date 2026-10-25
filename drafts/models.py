from django.db import models
from django.utils.translation import gettext_lazy as _

STATUS_CHOICES = [
    ("generated", _("Generated")),
    ("accepted", _("Accepted")),
]


class GenerationTask(models.Model):
    """An asynchronous draft generation, polled by the UI.

    Generation can take minutes (embedding model load, LLM call), so
    the request returns immediately and the page polls the status.
    """

    STATUS_CHOICES = [
        ("queued", _("Queued")),
        ("running", _("Running")),
        ("done", _("Done")),
        ("failed", _("Failed")),
    ]

    profile = models.ForeignKey(
        "profiles.Profile",
        verbose_name=_("Profile"),
        on_delete=models.CASCADE,
        related_name="generation_tasks",
    )
    request_type = models.CharField(_("Request type"), max_length=120)
    request_text = models.TextField(_("Request text"))
    instructions = models.TextField(
        _("Instructions"), blank=True, default=""
    )
    recipient_name = models.CharField(
        _("Recipient name"), max_length=255, blank=True, default=""
    )
    request_date = models.CharField(
        _("Request date"), max_length=64, blank=True, default=""
    )
    exclude_precedent_ids = models.JSONField(
        _("Excluded precedents"), default=list, blank=True
    )
    status = models.CharField(
        _("Status"), max_length=20, choices=STATUS_CHOICES, default="queued"
    )
    progress = models.CharField(
        _("Progress"), max_length=255, blank=True, default=""
    )
    error = models.TextField(_("Error"), blank=True, default="")
    generated_text = models.TextField(_("Generated text"), blank=True, default="")
    precedents_used = models.JSONField(
        _("Precedents used"), default=list, blank=True
    )
    created_at = models.DateTimeField(_("Created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated at"), auto_now=True)

    class Meta:
        verbose_name = _("Generation task")
        verbose_name_plural = _("Generation tasks")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.profile.name} / {self.request_type} / {self.pk}"


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
    instructions = models.TextField(
        _("Instructions"), blank=True, default=""
    )
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
