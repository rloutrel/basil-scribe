from django.db import models
from django.utils.translation import gettext_lazy as _

MATCH_SOURCE_CHOICES = [
    ("keyword", _("Subject keyword")),
    ("domain", _("Sender domain with type mention")),
    ("folder", _("Folder signal")),
]

MATCH_TYPE_CHOICES = [
    ("in_reply_to", _("In-Reply-To reference")),
    ("heuristic", _("Subject + date window heuristic")),
]


class ArchiveMail(models.Model):
    """One parsed `.eml` of the archive, per profile."""

    profile = models.ForeignKey(
        "profiles.Profile",
        verbose_name=_("Profile"),
        on_delete=models.CASCADE,
        related_name="archive_mails",
    )
    source_path = models.CharField(_("File path"), max_length=1024)
    folder = models.CharField(_("Folder"), max_length=512, blank=True, default="")
    message_id = models.CharField(_("Message-ID"), max_length=998, blank=True, default="")
    in_reply_to = models.CharField(
        _("In-Reply-To"), max_length=998, blank=True, default=""
    )
    references = models.TextField(_("References"), blank=True, default="")
    sender = models.CharField(_("Sender"), max_length=512, blank=True, default="")
    recipient = models.CharField(_("Recipient"), max_length=512, blank=True, default="")
    subject = models.CharField(_("Subject"), max_length=998, blank=True, default="")
    date = models.DateTimeField(_("Date"), null=True, blank=True)
    body = models.TextField(_("Body (plain text)"), blank=True, default="")
    is_outgoing = models.BooleanField(_("Outgoing (sent)"), default=False)

    class Meta:
        verbose_name = _("Archive mail")
        verbose_name_plural = _("Archive mails")
        unique_together = (("profile", "message_id", "source_path"),)
        indexes = [
            models.Index(fields=["profile", "message_id"]),
        ]

    def __str__(self):
        return self.subject or self.source_path


class Precedent(models.Model):
    """A (request, reply) pair usable as a few-shot example.

    Strictly scoped to one profile and one request type: similarity
    search never crosses profile or type boundaries.
    """

    profile = models.ForeignKey(
        "profiles.Profile",
        verbose_name=_("Profile"),
        on_delete=models.CASCADE,
        related_name="precedents",
    )
    request_type = models.CharField(_("Request type"), max_length=120)
    request_mail = models.ForeignKey(
        ArchiveMail,
        verbose_name=_("Request mail"),
        on_delete=models.CASCADE,
        related_name="precedents_as_request",
    )
    reply_mail = models.ForeignKey(
        ArchiveMail,
        verbose_name=_("Reply mail"),
        on_delete=models.CASCADE,
        related_name="precedents_as_reply",
    )
    match_source = models.CharField(
        _("Identification criterion"), max_length=20, choices=MATCH_SOURCE_CHOICES
    )
    match_type = models.CharField(
        _("Pairing method"), max_length=20, choices=MATCH_TYPE_CHOICES
    )
    answer_category = models.CharField(
        _("Answer category"), max_length=120, blank=True, default=""
    )
    embedding = models.JSONField(_("Request embedding"), null=True, blank=True)
    dedup_key = models.CharField(_("Deduplication key"), max_length=128, unique=True)
    created_at = models.DateTimeField(_("Created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated at"), auto_now=True)

    class Meta:
        verbose_name = _("Precedent")
        verbose_name_plural = _("Precedents")
        ordering = ["-request_mail__date"]

    def __str__(self):
        return f"{self.profile.name} / {self.request_type} / {self.pk}"


class ExtractionReport(models.Model):
    """End-of-run report of a `build_precedents` extraction."""

    profile = models.ForeignKey(
        "profiles.Profile",
        verbose_name=_("Profile"),
        on_delete=models.CASCADE,
        related_name="extraction_reports",
    )
    rebuilt = models.BooleanField(_("Full rebuild"), default=False)
    mails_parsed = models.PositiveIntegerField(_("Mails parsed"), default=0)
    mails_skipped = models.PositiveIntegerField(_("Mails skipped"), default=0)
    requests_identified = models.PositiveIntegerField(
        _("Requests identified"), default=0
    )
    pairs_matched = models.PositiveIntegerField(_("Pairs matched"), default=0)
    unanswered_requests = models.PositiveIntegerField(
        _("Requests without reply"), default=0
    )
    heuristic_matches = models.PositiveIntegerField(
        _("Heuristic matches"), default=0
    )
    unmatched_replies = models.PositiveIntegerField(
        _("Unmatched outgoing replies"), default=0
    )
    ambiguous_matches = models.PositiveIntegerField(_("Ambiguous matches"), default=0)
    per_type = models.JSONField(_("Per-type counts"), default=dict)
    per_criterion = models.JSONField(_("Per-criterion counts"), default=dict)
    created_at = models.DateTimeField(_("Created at"), auto_now_add=True)

    class Meta:
        verbose_name = _("Extraction report")
        verbose_name_plural = _("Extraction reports")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.profile.name} — {self.created_at}"
