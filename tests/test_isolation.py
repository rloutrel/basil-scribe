"""Profile isolation: a precedent of profile A is never offered to
profile B — neither by search nor by generation."""

from datetime import datetime, timezone
from unittest import mock

import pytest

from drafts.generation import generate_draft, similar_precedents
from precedents.models import ArchiveMail, Precedent

from .factories import make_eml, make_profile


def embedder_for(text):
    text = text.lower()
    if "künd" in text:
        return [1.0, 0.0, 0.0]
    if "devis" in text:
        return [0.0, 1.0, 0.0]
    return [0.0, 0.0, 1.0]


@pytest.fixture
def two_profiles(tmp_path, settings):
    settings.MAIL_EXPORT_ROOT = str(tmp_path)
    profile_a = make_profile(name="fk-roro", mail_source="fk-roro")
    profile_b = make_profile(
        name="corp", language="fr", mail_source="corp",
        request_types=[
            {
                "key": "quote",
                "name": "Demande de devis",
                "subject_keywords": ["devis"],
                "sender_domains": [],
                "folders": [],
                "answer_categories": ["acknowledge_receipt", "other"],
            }
        ],
    )
    # Archive for A: a resignation request and its sent reply.
    root_a = tmp_path / "fk-roro"
    make_eml(root_a, "1.eml", "Kündigung", "m@example.com",
             "Ich kündige meine Mitgliedschaft.",
             date="2026-01-10T10:00:00", message_id="<a1@x>", folder="Inbox")
    make_eml(root_a, "2.eml", "Re: Kündigung", "office@fk-roro.de",
             "Erhalten, Ende des Jahres.", date="2026-01-11T10:00:00",
             message_id="<a2@x>", in_reply_to="<a1@x>", folder="Sent")
    # Archive for B: a quote request and its sent reply.
    root_b = tmp_path / "corp"
    make_eml(root_b, "1.eml", "Demande de devis", "c@example.com",
             "Bonjour, pouvez-vous établir un devis ?",
             date="2026-02-01T10:00:00", message_id="<b1@x>", folder="Inbox")
    make_eml(root_b, "2.eml", "Re: Demande de devis", "info@corp.fr",
             "Bonjour, voici notre devis.", date="2026-02-02T10:00:00",
             message_id="<b2@x>", in_reply_to="<b1@x>", folder="Sent")

    from precedents.build import build_precedents

    with mock.patch(
        "precedents.build.embeddings.embed",
        side_effect=lambda text: embedder_for(text),
    ):
        build_precedents(profile_a)
        build_precedents(profile_b)
    return profile_a, profile_b


@pytest.mark.django_db
def test_precedents_scoped_by_profile(two_profiles):
    profile_a, profile_b = two_profiles
    assert Precedent.objects.filter(profile=profile_a).count() == 1
    assert Precedent.objects.filter(profile=profile_b).count() == 1


@pytest.mark.django_db
def test_search_never_crosses_profiles(two_profiles):
    profile_a, profile_b = two_profiles
    with mock.patch(
        "drafts.generation.embeddings.embed",
        side_effect=lambda text: embedder_for(text),
    ):
        found = similar_precedents(
            profile_b, "quote", "Demande de devis urgent"
        )
    ids = {p.profile_id for p in found}
    assert found
    assert ids == {profile_b.id}


@pytest.mark.django_db
def test_generation_uses_only_own_profile_precedents(two_profiles):
    profile_a, profile_b = two_profiles
    with mock.patch(
        "drafts.generation.embeddings.embed",
        side_effect=lambda text: embedder_for(text),
    ), mock.patch(
        "drafts.generation.llm.complete", return_value="Bonjour, voici la réponse."
    ) as complete:
        text, precedents = generate_draft(
            profile_b, "quote", "Pouvez-vous me faire un devis ?"
        )
    assert text == "Bonjour, voici la réponse."
    prompt = complete.call_args[0][0]
    assert "devis" in prompt.lower()
    assert "Kündigung" not in prompt
    assert precedents
    assert precedents[0]["request_subject"] == "Demande de devis"


@pytest.mark.django_db
def test_search_scoped_by_request_type(tmp_path, settings):
    settings.MAIL_EXPORT_ROOT = str(tmp_path)
    profile = make_profile()
    root = tmp_path / "fk-roro"
    make_eml(root, "1.eml", "Kündigung", "m@example.com", "kündigung body",
             date="2026-01-10T10:00:00", message_id="<a1@x>", folder="Inbox")
    make_eml(root, "2.eml", "Re: Kündigung", "office@fk-roro.de", "ok",
             date="2026-01-11T10:00:00", message_id="<a2@x>",
             in_reply_to="<a1@x>", folder="Sent")
    make_eml(root, "3.eml", "Aufnahme", "n@example.com", "aufnahme body",
             date="2026-03-10T10:00:00", message_id="<a3@x>", folder="Inbox")
    make_eml(root, "4.eml", "Re: Aufnahme", "office@fk-roro.de", "ok",
             date="2026-03-11T10:00:00", message_id="<a4@x>",
             in_reply_to="<a3@x>", folder="Sent")
    from precedents.build import build_precedents

    with mock.patch(
        "precedents.build.embeddings.embed",
        side_effect=lambda text: embedder_for(text),
    ):
        build_precedents(profile)
    with mock.patch(
        "drafts.generation.embeddings.embed",
        side_effect=lambda text: embedder_for(text),
    ):
        found = similar_precedents(profile, "application", "aufnahme bitte")
    assert {p.request_type for p in found} == {"application"}
