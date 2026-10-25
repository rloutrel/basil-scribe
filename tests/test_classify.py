"""Batch classification command: LLM mocked, tolerant parsing."""

from datetime import datetime, timezone
from unittest import mock

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from precedents.models import ArchiveMail, Precedent

from .factories import make_profile


def _make_pair(profile, subject="Kündigung", reply="Erhalten.", seq=1):
    date = datetime(2026, 1, seq, 10, tzinfo=timezone.utc)
    request = ArchiveMail.objects.create(
        profile=profile,
        source_path=f"a{seq}",
        message_id=f"<r{seq}@x>",
        subject=subject,
        sender="m@example.com",
        date=date,
        body="Ich kündige.",
        is_outgoing=False,
    )
    reply_mail = ArchiveMail.objects.create(
        profile=profile,
        source_path=f"s{seq}",
        message_id=f"<s{seq}@x>",
        in_reply_to=f"<r{seq}@x>",
        subject=f"Re: {subject}",
        sender="office@fk-roro.de",
        date=date,
        body=reply,
        is_outgoing=True,
    )
    return Precedent.objects.create(
        profile=profile,
        request_type="resignation",
        request_mail=request,
        reply_mail=reply_mail,
        match_source="keyword",
        match_type="in_reply_to",
        embedding=[1.0, 0.0],
        dedup_key=f"cls{seq}",
    )


@pytest.fixture
def profile(db):
    return make_profile()


def test_classify_assigns_categories(profile):
    first = _make_pair(profile, reply="Erhalten.", seq=1)
    second = _make_pair(profile, reply="Bestätigt.", seq=2)
    prompts = []

    def fake_complete(prompt, temperature=0.0):
        prompts.append(prompt)
        return {
            prompts[0]: '{"category": "confirm_end"}',
        }.get(
            prompt,
            'Blabla {"category": "acknowledge_receipt"} blabla',
        )

    with mock.patch(
        "precedents.management.commands.classify_precedents.llm.complete",
        side_effect=fake_complete,
    ) as complete:
        call_command("classify_precedents", "--profile", profile.name)
    assert complete.call_count == 2
    first.refresh_from_db()
    second.refresh_from_db()
    assert {first.answer_category, second.answer_category} == {
        "confirm_end",
        "acknowledge_receipt",
    }
    for prompt in prompts:
        assert '"category"' in prompt


def test_classify_unknown_category_is_not_fatal(profile):
    _make_pair(profile, seq=1)
    with mock.patch(
        "precedents.management.commands.classify_precedents.llm.complete",
        return_value='{"category": "not_a_category"}',
    ):
        call_command("classify_precedents", "--profile", profile.name)
    assert Precedent.objects.get(profile=profile).answer_category == ""


def test_classify_unparseable_answer_is_not_fatal(profile):
    _make_pair(profile, seq=1)
    with mock.patch(
        "precedents.management.commands.classify_precedents.llm.complete",
        return_value="I do not understand.",
    ):
        call_command("classify_precedents", "--profile", profile.name)
    assert Precedent.objects.get(profile=profile).answer_category == ""


def test_classify_all_failures_reported(profile, capsys):
    from core.llm import LLMError

    _make_pair(profile, seq=1)
    with mock.patch(
        "precedents.management.commands.classify_precedents.llm.complete",
        side_effect=LLMError("boom"),
    ):
        call_command("classify_precedents", "--profile", profile.name)
    assert "failed" in capsys.readouterr().out
    assert Precedent.objects.get(profile=profile).answer_category == ""


def test_classify_no_unclassified(profile):
    with mock.patch(
        "precedents.management.commands.classify_precedents.llm.complete"
    ) as complete:
        call_command("classify_precedents", "--profile", profile.name)
    assert complete.call_count == 0


@pytest.mark.django_db
def test_classify_unknown_profile_raises():
    with pytest.raises(CommandError):
        call_command("classify_precedents", "--profile", "ghost")
