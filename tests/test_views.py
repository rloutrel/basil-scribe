"""Views, draft lifecycle (steps 3–4) and the profile selector."""

from unittest import mock

import pytest
from django.urls import reverse

from drafts.models import Draft
from precedents.models import Precedent

from .factories import make_profile


@pytest.fixture
def profile(db):
    return make_profile()


@pytest.fixture
def client_with_profile(client, profile):
    session = client.session
    session["active_profile"] = profile.name
    session.save()
    return client


def test_home_requires_active_profile(db, client):
    response = client.get(reverse("drafts:home"))
    assert response.status_code == 200
    assert b"No profile" in response.content or "profile" in response.context


def test_home_with_profile(client_with_profile, profile):
    response = client_with_profile.get(reverse("drafts:home"))
    assert response.status_code == 200
    assert profile.display_name.encode() in response.content


def test_generate_stores_payload_in_session(client_with_profile, profile):
    with mock.patch(
        "drafts.generation.llm.complete", return_value="Sehr geehrter Herr X, …"
    ) as complete, mock.patch(
        "drafts.generation.embeddings.embed", return_value=[1.0, 0.0]
    ):
        response = client_with_profile.post(
            reverse("drafts:generate"),
            {
                "request_type": "resignation",
                "request_text": "Ich kündige meine Mitgliedschaft.",
                "recipient_name": "Herr X",
                "request_date": "2026-02-01",
            },
        )
    assert response.status_code == 302
    payload = client_with_profile.session["draft_payload"]
    assert payload["generated_text"].startswith("Sehr geehrter")
    assert payload["request_type"] == "resignation"
    prompt = complete.call_args[0][0]
    assert "Du bist ein Vorstandsmitglied." in prompt
    assert "Die Mitgliedschaft endet zum Ende des Kalenderjahres." in prompt
    assert "Mit freundlichen Grüßen" in prompt


def test_generate_requires_text(client_with_profile, profile):
    response = client_with_profile.post(
        reverse("drafts:generate"), {"request_type": "resignation"}
    )
    assert response.status_code == 302
    assert "draft_payload" not in client_with_profile.session


def test_generate_unknown_type_rejected(client_with_profile, profile):
    with mock.patch("drafts.generation.embeddings.embed", return_value=[1.0]):
        response = client_with_profile.post(
            reverse("drafts:generate"),
            {"request_type": "nope", "request_text": "Hallo"},
        )
    assert response.status_code == 302
    assert "draft_payload" not in client_with_profile.session


def test_generate_llm_failure_is_non_fatal(client_with_profile, profile):
    from core.llm import LLMError

    with mock.patch(
        "drafts.generation.embeddings.embed", return_value=[1.0]
    ), mock.patch(
        "drafts.generation.llm.complete",
        side_effect=LLMError("connection refused"),
    ):
        response = client_with_profile.post(
            reverse("drafts:generate"),
            {"request_type": "resignation", "request_text": "Ich kündige."},
        )
    assert response.status_code == 302


def test_regenerate_excludes_precedent(client_with_profile, profile, db):
    session = client_with_profile.session
    session["draft_payload"] = {
        "request_type": "resignation",
        "request_text": "Ich kündige.",
        "recipient_name": "",
        "request_date": "",
        "precedents_used": [{"id": 42, "request_subject": "s", "reply_body": "r"}],
    }
    session.save()
    with mock.patch(
        "drafts.generation.embeddings.embed", return_value=[1.0]
    ), mock.patch(
        "drafts.generation.llm.complete", return_value="Version 2"
    ) as complete, mock.patch(
        "drafts.generation.similar_precedents", return_value=[]
    ) as similar:
        client_with_profile.post(reverse("drafts:regenerate"))
    assert client_with_profile.session["draft_payload"]["generated_text"] == "Version 2"
    kwargs = similar.call_args.kwargs
    assert kwargs["exclude_ids"] == ["42"]


def test_draft_list_and_accept(client_with_profile, profile):
    draft = Draft.objects.create(
        profile=profile,
        request_type="resignation",
        request_text="Ich kündige.",
        generated_text="Sehr geehrte Damen…",
    )
    response = client_with_profile.get(reverse("drafts:draft_list"))
    assert draft.request_type in response.context["drafts"][0].request_type
    response = client_with_profile.post(
        reverse("drafts:accept", args=[draft.pk]),
        {"final_text": "Sehr geehrte Damen, final version."},
    )
    draft.refresh_from_db()
    assert draft.status == "accepted"
    assert draft.final_text == "Sehr geehrte Damen, final version."


def test_accept_requires_text(client_with_profile, profile):
    draft = Draft.objects.create(
        profile=profile, request_type="resignation", request_text="x"
    )
    client_with_profile.post(reverse("drafts:accept", args=[draft.pk]), {})
    draft.refresh_from_db()
    assert draft.status == "generated"


def test_accept_scoped_to_active_profile(client_with_profile, profile, db):
    other = make_profile(name="other")
    draft = Draft.objects.create(
        profile=other, request_type="quote", request_text="x"
    )
    response = client_with_profile.post(
        reverse("drafts:accept", args=[draft.pk]), {"final_text": "y"}
    )
    assert response.status_code == 404


def test_add_precedent_from_accepted_draft(client_with_profile, profile):
    draft = Draft.objects.create(
        profile=profile,
        request_type="resignation",
        request_text="Ich kündige.",
        generated_text="Brouillon",
        final_text="Finale Antwort",
        status="accepted",
    )
    with mock.patch(
        "precedents.build.embeddings.embed", return_value=[1.0, 0.0]
    ):
        response = client_with_profile.post(
            reverse("drafts:add_precedent", args=[draft.pk])
        )
    assert response.status_code == 302
    draft.refresh_from_db()
    assert draft.added_as_precedent is True
    assert Precedent.objects.filter(profile=profile).count() == 1
    precedent = Precedent.objects.get(profile=profile)
    assert precedent.reply_mail.body == "Finale Antwort"


def test_profile_selector_switches_session(client, profile, db):
    other = make_profile(name="corp", display_name="Corp")
    response = client.post(
        reverse("profiles:select"), {"profile": "corp", "next": "/"}
    )
    assert response.status_code == 302
    assert client.session["active_profile"] == "corp"


def test_profile_selector_rejects_unknown(client, profile, db):
    response = client.post(reverse("profiles:select"), {"profile": "ghost"})
    assert response.status_code == 404
