import json

from django.db import models
from django.utils.translation import gettext_lazy as _


class Profile(models.Model):
    """A correspondence profile synced from `profiles/<name>.yaml`.

    All precedent and draft models carry a foreign key to this model:
    profiles are fully isolated from each other.
    """

    name = models.CharField(_("Profile name"), max_length=120, unique=True)
    display_name = models.CharField(_("Displayed name"), max_length=255)
    filename = models.CharField(_("File name"), max_length=255)
    language = models.CharField(_("Language"), max_length=10)
    mail_source = models.CharField(_("Mail source folder"), max_length=255)
    organization_name = models.CharField(_("Organization"), max_length=255)
    greeting = models.CharField(_("Greeting form"), max_length=64)
    signature = models.TextField(_("Signature"))
    rules = models.TextField(_("Business rules"), blank=True, default="")
    role_prompt = models.TextField(_("Role prompt"))
    temperature = models.FloatField(
        _("Generation temperature"), default=0.7
    )
    request_types = models.JSONField(_("Request types"), default=list)
    context_enabled = models.BooleanField(_("Context enabled"), default=False)
    enabled = models.BooleanField(_("Enabled"), default=True)

    class Meta:
        verbose_name = _("Profile")
        verbose_name_plural = _("Profiles")
        ordering = ["name"]

    def __str__(self):
        return self.display_name or self.name

    def request_type(self, key):
        for rt in self.request_types:
            if rt.get("key") == key:
                return rt
        return None

    def request_type_keys(self):
        return [rt.get("key") for rt in self.request_types if rt.get("key")]

    @classmethod
    def from_config(cls, config):
        """Create or update this profile from a ProfileConfig snapshot."""
        request_types = [
            {
                "key": rt.key,
                "name": rt.name,
                "subject_keywords": rt.subject_keywords,
                "sender_domains": rt.sender_domains,
                "folders": rt.folders,
                "answer_categories": rt.answer_categories,
            }
            for rt in config.request_types
        ]
        profile, _ = cls.objects.update_or_create(
            name=config.name,
            defaults={
                "display_name": config.name,
                "filename": config.filename,
                "language": config.language,
                "mail_source": config.mail_source,
                "organization_name": config.organization_name,
                "greeting": config.greeting,
                "signature": config.signature,
                "rules": config.rules,
                "role_prompt": config.role_prompt,
                "temperature": config.temperature,
                "request_types": request_types,
                "context_enabled": config.context_enabled,
            },
        )
        return profile


class ProfileSyncResult(models.Model):
    """Audit trail of one profile sync run."""

    name = models.CharField(_("Profile name"), max_length=120)
    success = models.BooleanField(_("Success"))
    errors = models.TextField(_("Errors"), blank=True, default="")
    created_at = models.DateTimeField(_("Created at"), auto_now_add=True)

    class Meta:
        verbose_name = _("Profile sync result")
        verbose_name_plural = _("Profile sync results")
        ordering = ["-created_at"]

    def __str__(self):
        return self.name

    def error_list(self):
        try:
            return json.loads(self.errors or "[]")
        except ValueError:
            return []
