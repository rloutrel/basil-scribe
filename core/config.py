"""
Loading and validation of profile YAML files.

This module turns a `profiles/<name>.yaml` file into a `ProfileConfig`
object. All validation errors are reported through the profile's own
`language`, so the maintainer reads actionable messages in their working
language.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from django.conf import settings
from django.utils.translation import gettext as _

logger = logging.getLogger(__name__)

LANGUAGE_CODES = {"en", "fr", "de"}


class ConfigError(Exception):
    """A profile file is invalid; message is in the profile language."""

    def __init__(self, message, errors=None):
        super().__init__(message)
        self.errors = list(errors or [])


@dataclass
class RequestTypeConfig:
    key: str
    name: str
    subject_keywords: list = field(default_factory=list)
    sender_domains: list = field(default_factory=list)
    folders: list = field(default_factory=list)
    answer_categories: list = field(default_factory=list)


@dataclass
class ProfileConfig:
    name: str
    filename: str
    language: str
    mail_source: str
    organization_name: str
    greeting: str
    signature: str
    rules: str
    role_prompt: str
    temperature: float
    request_types: list = field(default_factory=list)
    context_enabled: bool = False

    def request_type(self, key):
        for rt in self.request_types:
            if rt.key == key:
                return rt
        return None


def profile_dir():
    return Path(settings.PROFILES_DIR)


def _raw(value, errors, key, language):
    if value is None:
        errors.append(_("Missing key '%(key)s' in profile file.") % {"key": key})
        return ""
    if not isinstance(value, str) or not value.strip():
        errors.append(_("Key '%(key)s' must be a non-empty string.") % {"key": key})
        return ""
    return value


def _str_list(value, errors, key, language, allow_empty=True):
    if value is None:
        return []
    if not isinstance(value, list):
        errors.append(_("Key '%(key)s' must be a list of strings.") % {"key": key})
        return []
    if not value and not allow_empty:
        errors.append(_("Key '%(key)s' must be a non-empty list of strings.") % {"key": key})
        return []
    clean = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            errors.append(_("Key '%(key)s' must only contain non-empty strings.") % {"key": key})
        else:
            clean.append(item)
    return clean


def load_profile_file(path):
    """Load and validate a single profile file; raise ConfigError."""
    path = Path(path)
    try:
        raw_text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigError(str(exc))
    try:
        data = yaml.safe_load(raw_text)
    except yaml.YAMLError as exc:
        raise ConfigError(_("Invalid YAML: %(error)s") % {"error": exc})
    if not isinstance(data, dict):
        raise ConfigError(_("Invalid YAML: the file must contain a mapping."))

    profile = data.get("profile") or {}
    if not isinstance(profile, dict):
        raise ConfigError(_("Key 'profile' must be a mapping."))
    language = str(profile.get("language") or "").strip().lower()
    # Activate the profile language so further errors are rendered in it.
    from django.utils import translation

    with translation.override(language or "en"):
        errors = []
        name = _raw(profile.get("name"), errors, "profile.name", language)
        if not language:
            errors.append(_("Missing key '%(key)s' in profile file.") % {"key": "profile.language"})
        elif language not in LANGUAGE_CODES:
            errors.append(
                _("Key '%(key)s' must be one of: %(codes)s.")
                % {"key": "profile.language", "codes": ", ".join(sorted(LANGUAGE_CODES))}
            )
        mail_source = _raw(profile.get("mail_source"), errors, "profile.mail_source", language)

        organization = data.get("organization") or {}
        if not isinstance(organization, dict):
            errors.append(_("Key 'organization' must be a mapping."))
            organization = {}
        org_name = _raw(organization.get("name"), errors, "organization.name", language)
        greeting = _raw(organization.get("greeting"), errors, "organization.greeting", language)
        signature = _raw(organization.get("signature"), errors, "organization.signature", language)
        rules = organization.get("rules") or ""
        if not isinstance(rules, str):
            errors.append(_("Key '%(key)s' must be a string.") % {"key": "organization.rules"})
            rules = ""

        role_prompt = _raw(data.get("role_prompt"), errors, "role_prompt", language)

        temperature = data.get("temperature")
        if temperature is not None:
            if not isinstance(temperature, (int, float)):
                errors.append(_("Key 'temperature' must be a number."))
                temperature = settings.DEFAULT_LLM_TEMPERATURE
        else:
            temperature = settings.DEFAULT_LLM_TEMPERATURE

        request_types = []
        rt_data = data.get("request_types")
        if not isinstance(rt_data, dict) or not rt_data:
            errors.append(
                _("Key 'request_types' must be a mapping with at least one entry.")
            )
        else:
            for key, item in rt_data.items():
                if not isinstance(item, dict):
                    errors.append(
                        _("Request type '%(type)s' must be a mapping.")
                        % {"type": key}
                    )
                    continue
                rt_errors = []
                rt_name = _raw(item.get("name"), rt_errors, f"request_types.{key}.name", language)
                keywords = _str_list(
                    item.get("subject_keywords"),
                    rt_errors,
                    f"request_types.{key}.subject_keywords",
                    language,
                    allow_empty=False,
                )
                domains = _str_list(
                    item.get("sender_domains"),
                    rt_errors,
                    f"request_types.{key}.sender_domains",
                    language,
                )
                folders = _str_list(
                    item.get("folders"),
                    rt_errors,
                    f"request_types.{key}.folders",
                    language,
                )
                categories = _str_list(
                    item.get("answer_categories"),
                    rt_errors,
                    f"request_types.{key}.answer_categories",
                    language,
                    allow_empty=False,
                )
                if not categories:
                    rt_errors.append(
                        _("Request type '%(type)s' must define at least one answer category.")
                        % {"type": key}
                    )
                errors.extend(rt_errors)
                if not rt_errors:
                    request_types.append(
                        RequestTypeConfig(
                            key=key,
                            name=rt_name,
                            subject_keywords=keywords,
                            sender_domains=domains,
                            folders=folders,
                            answer_categories=categories,
                        )
                    )

        context = data.get("context")
        context_enabled = False
        if context is not None:
            if not isinstance(context, dict):
                errors.append(_("Key 'context' must be a mapping."))
            else:
                context_enabled = bool(context.get("enabled", False))

        if errors:
            raise ConfigError(
                _("The profile is invalid: %(count)d error(s).")
                % {"count": len(errors)},
                errors=errors,
            )

    return ProfileConfig(
        name=name,
        filename=path.name,
        language=language,
        mail_source=mail_source,
        organization_name=org_name,
        greeting=greeting,
        signature=signature,
        rules=rules,
        role_prompt=role_prompt,
        temperature=float(temperature),
        request_types=request_types,
        context_enabled=context_enabled,
    )


def load_profile(name):
    """Load the profile file `profiles/<name>.yaml` (name without suffix)."""
    return load_profile_file(profile_dir() / f"{name}.yaml")


def available_profile_names():
    return sorted(p.stem for p in profile_dir().glob("*.yaml"))


def ensure_example_profile():
    """Copy the shipped example profile if the profiles dir is empty."""
    target_dir = profile_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    if target_dir != Path(settings.BASE_DIR) / "profiles" or any(
        target_dir.glob("*.yaml")
    ):
        return
    source = Path(settings.BASE_DIR) / "profiles" / "example.yaml"
    target = target_dir / "example.yaml"
    if source != target and source.exists() and not target.exists():
        target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
