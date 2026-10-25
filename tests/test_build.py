"""build_precedents end-to-end on fixture archives (embeddings mocked)."""

from datetime import datetime, timezone
from unittest import mock

import pytest
from django.core.management import call_command

from precedents.build import build_precedents, dedup_key
from precedents.models import ArchiveMail, Precedent

from .factories import make_eml, make_profile

pytestmark = pytest.mark.django_db


def fake_embed(text):
    return [1.0, 0.0, 0.0]


def _archive(tmp_path, source="fk-roro"):
    return tmp_path / source


def test_build_creates_pairs_and_report(tmp_path, settings):
    settings.MAIL_EXPORT_ROOT = str(tmp_path)
    root = _archive(tmp_path)
    make_eml(root, "1.eml", "Kündigung der Mitgliedschaft",
             "mitglied@example.com", "Ich kündige.",
             date="2026-01-10T10:00:00", message_id="<r1@x>",
             folder="Inbox")
    make_eml(root, "2.eml", "Re: Kündigung der Mitgliedschaft",
             "office@fk-roro.de", "Wir haben Ihre Kündigung erhalten.",
             date="2026-01-11T10:00:00", message_id="<s1@x>",
             in_reply_to="<r1@x>", folder="Sent")
    profile = make_profile()

    with mock.patch("precedents.build.embeddings.embed", side_effect=fake_embed):
        report = build_precedents(profile)

    assert report.mails_parsed == 2
    assert report.requests_identified == 1
    assert report.per_type == {"resignation": 1}
    assert report.per_criterion == {"keyword": 1}
    assert report.pairs_matched == 1
    assert report.unanswered_requests == 0
    assert report.heuristic_matches == 0
    pair = Precedent.objects.get(profile=profile)
    assert pair.request_mail.message_id == "<r1@x>"
    assert pair.reply_mail.message_id == "<s1@x>"
    assert pair.match_type == "in_reply_to"
    assert pair.embedding == fake_embed("")


def test_build_unanswered_request_logged(tmp_path, settings):
    settings.MAIL_EXPORT_ROOT = str(tmp_path)
    root = _archive(tmp_path)
    make_eml(root, "1.eml", "Kündigung", "m@example.com", "Ich kündige.",
             date="2026-01-10T10:00:00", message_id="<r1@x>", folder="Inbox")
    profile = make_profile()
    with mock.patch("precedents.build.embeddings.embed", side_effect=fake_embed):
        report = build_precedents(profile)
    assert report.requests_identified == 1
    assert report.unanswered_requests == 1
    assert report.pairs_matched == 0
    assert Precedent.objects.count() == 0


def test_build_heuristic_pairing(tmp_path, settings):
    settings.MAIL_EXPORT_ROOT = str(tmp_path)
    root = _archive(tmp_path)
    make_eml(root, "1.eml", "Kündigung", "m@example.com", "Ich kündige.",
             date="2026-01-10T10:00:00", message_id="<r1@x>", folder="Inbox")
    make_eml(root, "2.eml", "Re: Kündigung", "office@fk-roro.de",
             "Erhalten.", date="2026-01-12T10:00:00",
             message_id="<s1@x>", folder="Sent")
    profile = make_profile()
    with mock.patch("precedents.build.embeddings.embed", side_effect=fake_embed):
        report = build_precedents(profile)
    assert report.pairs_matched == 1
    assert report.heuristic_matches == 1
    pair = Precedent.objects.get(profile=profile)
    assert pair.match_type == "heuristic"


def test_build_is_idempotent(tmp_path, settings):
    settings.MAIL_EXPORT_ROOT = str(tmp_path)
    root = _archive(tmp_path)
    make_eml(root, "1.eml", "Kündigung", "m@example.com", "Ich kündige.",
             date="2026-01-10T10:00:00", message_id="<r1@x>", folder="Inbox")
    make_eml(root, "2.eml", "Re: Kündigung", "office@fk-roro.de",
             "Erhalten.", date="2026-01-11T10:00:00",
             message_id="<s1@x>", in_reply_to="<r1@x>", folder="Sent")
    profile = make_profile()
    with mock.patch("precedents.build.embeddings.embed", side_effect=fake_embed):
        build_precedents(profile)
        build_precedents(profile)
    assert Precedent.objects.filter(profile=profile).count() == 1


def test_build_rebuild_clears(tmp_path, settings):
    settings.MAIL_EXPORT_ROOT = str(tmp_path)
    root = _archive(tmp_path)
    make_eml(root, "1.eml", "Kündigung", "m@example.com", "Ich kündige.",
             date="2026-01-10T10:00:00", message_id="<r1@x>", folder="Inbox")
    make_eml(root, "2.eml", "Re: Kündigung", "office@fk-roro.de",
             "Erhalten.", date="2026-01-11T10:00:00",
             message_id="<s1@x>", in_reply_to="<r1@x>", folder="Sent")
    profile = make_profile()
    with mock.patch("precedents.build.embeddings.embed", side_effect=fake_embed):
        build_precedents(profile)
        assert ArchiveMail.objects.count() == 2
        build_precedents(profile, rebuild=True)
        assert ArchiveMail.objects.count() == 2
        assert Precedent.objects.count() == 1


def test_build_never_writes_archive(tmp_path, settings):
    settings.MAIL_EXPORT_ROOT = str(tmp_path)
    root = _archive(tmp_path)
    make_eml(root, "1.eml", "Kündigung", "m@example.com", "Ich kündige.",
             date="2026-01-10T10:00:00", message_id="<r1@x>", folder="Inbox")
    before = {p.name: p.stat().st_mtime for p in root.rglob("*.eml")}
    profile = make_profile()
    with mock.patch("precedents.build.embeddings.embed", side_effect=fake_embed):
        build_precedents(profile)
    after = {p.name: p.stat().st_mtime for p in root.rglob("*.eml")}
    assert before == after


def test_dedup_key_deterministic():
    a = dedup_key(1, "<x@y>", datetime(2026, 1, 1, tzinfo=timezone.utc))
    b = dedup_key(1, "<x@y>", datetime(2026, 1, 1, tzinfo=timezone.utc))
    c = dedup_key(2, "<x@y>", datetime(2026, 1, 1, tzinfo=timezone.utc))
    assert a == b
    assert a != c


def test_command_build_precedents(tmp_path, settings, capsys):
    settings.MAIL_EXPORT_ROOT = str(tmp_path)
    root = _archive(tmp_path)
    make_eml(root, "1.eml", "Kündigung", "m@example.com", "Ich kündige.",
             date="2026-01-10T10:00:00", message_id="<r1@x>", folder="Inbox")
    profile = make_profile()
    with mock.patch("precedents.build.embeddings.embed", side_effect=fake_embed):
        call_command("build_precedents", "--profile", profile.name)
    out = capsys.readouterr().out
    assert "Extraktionsbericht" in out  # report rendered in the profile language
