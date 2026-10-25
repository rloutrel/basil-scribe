"""Profile YAML loading and validation; errors in the profile language."""

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from core import config
from profiles.models import Profile, ProfileSyncResult
from profiles.sync import sync_all, sync_profile

from .factories import PROFILE_A_REQUEST_TYPES

FULL_DE = """
profile:
  name: "Förderkreis"
  language: "de"
  mail_source: "fk-roro"

organization:
  name: "Förderkreis e.V."
  greeting: "Sie"
  signature: |
    Mit freundlichen Grüßen
  rules: |
    Regel eins.

role_prompt: |
  Du bist Vorstand.

request_types:
  resignation:
    name: "Kündigung"
    subject_keywords: ["kündigung"]
    sender_domains: ["fk-roro.de"]
    folders: ["Kündigung_*"]
    answer_categories: ["acknowledge_receipt", "other"]
"""

FULL_FR = FULL_DE.replace('language: "de"', 'language: "fr"')


def load_from(tmp_path, content, name="test"):
    path = tmp_path / f"{name}.yaml"
    path.write_text(content, encoding="utf-8")
    return config.load_profile_file(path)


def test_load_full_profile(tmp_path):
    cfg = load_from(tmp_path, FULL_DE)
    assert cfg.name == "Förderkreis"
    assert cfg.language == "de"
    assert cfg.mail_source == "fk-roro"
    assert cfg.organization_name == "Förderkreis e.V."
    assert cfg.temperature == pytest.approx(
        __import__("django.conf", fromlist=["settings"]).settings.DEFAULT_LLM_TEMPERATURE
    )
    assert cfg.request_types[0].key == "resignation"
    assert cfg.request_types[0].answer_categories == ["acknowledge_receipt", "other"]


def test_missing_required_keys_reported_in_profile_language(tmp_path):
    with pytest.raises(config.ConfigError) as exc_info:
        load_from(tmp_path, "profile:\n  name: 'X'\n  language: 'de'\n")
    messages = [str(exc_info.value)] + [str(e) for e in exc_info.value.errors]
    assert any("profile.mail_source" in m for m in messages)
    assert any("organization" in m or "organization" in str(m) for m in messages)


def test_missing_language(tmp_path):
    with pytest.raises(config.ConfigError) as exc_info:
        load_from(tmp_path, FULL_DE.replace('language: "de"', ""))
    assert any("profile.language" in str(e) for e in exc_info.value.errors)


def test_type_without_categories(tmp_path):
    broken = FULL_DE.replace(
        "answer_categories: [\"acknowledge_receipt\", \"other\"]", ""
    )
    with pytest.raises(config.ConfigError) as exc_info:
        load_from(tmp_path, broken)
    assert any(
        "antwortkategorie" in str(e).lower() for e in exc_info.value.errors
    )  # error rendered in the profile language (de)


def test_empty_value(tmp_path):
    broken = FULL_DE.replace('greeting: "Sie"', 'greeting: ""')
    with pytest.raises(config.ConfigError) as exc_info:
        load_from(tmp_path, broken)
    assert any("organization.greeting" in str(e) for e in exc_info.value.errors)


def test_no_request_types(tmp_path):
    broken = FULL_DE.split("request_types:")[0]
    with pytest.raises(config.ConfigError) as exc_info:
        load_from(tmp_path, broken)
    assert any("request_types" in str(e) for e in exc_info.value.errors)


def test_unknown_language(tmp_path):
    broken = FULL_DE.replace('language: "de"', 'language: "xx"')
    with pytest.raises(config.ConfigError):
        load_from(tmp_path, broken)


def test_temperature_override(tmp_path):
    cfg = load_from(tmp_path, FULL_DE + "\ntemperature: 0.2\n")
    assert cfg.temperature == pytest.approx(0.2)


def test_context_key_accepted_disabled(tmp_path):
    cfg = load_from(tmp_path, FULL_DE + "\ncontext:\n  enabled: false\n")
    assert cfg.context_enabled is False


@pytest.mark.django_db
def test_sync_profile_and_all(tmp_path, settings):
    settings.PROFILES_DIR = tmp_path
    (tmp_path / "ok.yaml").write_text(FULL_DE, encoding="utf-8")
    (tmp_path / "bad.yaml").write_text("profile:\n  name: 'Bad'\n", encoding="utf-8")
    results = dict((name, success) for name, success, _ in sync_all())
    assert results["ok"] is True
    assert results["bad"] is False
    assert Profile.objects.filter(name="Förderkreis").exists()
    assert ProfileSyncResult.objects.filter(name="bad", success=False).exists()


@pytest.mark.django_db
def test_check_config_command(tmp_path, settings, capsys):
    settings.PROFILES_DIR = tmp_path
    (tmp_path / "ok.yaml").write_text(FULL_FR, encoding="utf-8")
    (tmp_path / "bad.yaml").write_text("profile: {}\n", encoding="utf-8")
    with pytest.raises(CommandError):
        call_command("check_config")
    out = capsys.readouterr()
    assert "ok" in out.out
    call_command("check_config", "--profile", "ok", "--sync")
    assert Profile.objects.filter(name="Förderkreis").exists()
    with pytest.raises(CommandError):
        call_command("check_config", "--profile", "missing")


@pytest.mark.django_db
def test_example_profile_shipped_in_repo_is_valid(tmp_path, settings):
    import shutil
    from pathlib import Path

    repo_profiles = Path(__file__).resolve().parents[1] / "profiles"
    settings.PROFILES_DIR = tmp_path
    shutil.copy(repo_profiles / "example.yaml", tmp_path / "example.yaml")
    cfg = config.load_profile("example")
    assert cfg.language == "de"
    assert cfg.request_types
    sync_profile(cfg)
    assert Profile.objects.filter(name=cfg.name).exists()
