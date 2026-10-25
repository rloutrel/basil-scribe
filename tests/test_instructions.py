"""Free-form instructions injected into the generation prompt."""

from unittest import mock

import pytest
from django.urls import reverse

from drafts.models import GenerationTask
from precedents.prompts import generation_prompt

from .factories import make_profile


@pytest.fixture
def profile(db):
    return make_profile()


def test_instructions_block_order_in_prompt():
    prompt = generation_prompt(
        profile_language="de",
        role_prompt="Du bist Vorstand.",
        organization_rules="Regel A.",
        request_text="Ich kündige.",
        precedents=[],
        greeting="Sie",
        signature="MfG",
        instructions="Erwähne die Mitgliederversammlung.",
    )
    assert prompt.index("Regel A.") < prompt.index(
        "Zusätzliche Anweisungen für diese Antwort:"
    )
    assert prompt.index("Zusätzliche Anweisungen") < prompt.index("Ich kündige.")
    assert "Erwähne die Mitgliederversammlung." in prompt


def test_instructions_block_per_language():
    for language, needle in (
        ("de", "Zusätzliche Anweisungen für diese Antwort:"),
        ("fr", "Instructions supplémentaires pour cette réponse :"),
        ("en", "Additional instructions for this reply:"),
    ):
        prompt = generation_prompt(
            profile_language=language,
            role_prompt="r",
            organization_rules="",
            request_text="x",
            precedents=[],
            greeting="g",
            signature="s",
            instructions="do this",
        )
        assert needle in prompt


def test_no_instructions_no_block():
    prompt = generation_prompt(
        profile_language="de",
        role_prompt="r",
        organization_rules="rules",
        request_text="x",
        precedents=[],
        greeting="g",
        signature="s",
        instructions="   ",
    )
    assert "Anweisungen" not in prompt


@pytest.mark.django_db
def test_instructions_flow_from_form_to_prompt(client, profile):
    session = client.session
    session["active_profile"] = profile.name
    session.save()
    with mock.patch(
        "drafts.generation.llm.complete", return_value="Antwort"
    ) as complete, mock.patch(
        "drafts.generation.embeddings.embed", return_value=[1.0, 0.0]
    ):
        client.post(
            reverse("drafts:generate"),
            {
                "request_type": "resignation",
                "request_text": "Ich kündige.",
                "instructions": "Sei besonders kurz.",
            },
        )
        task = GenerationTask.objects.get(profile=profile)
        assert task.instructions == "Sei besonders kurz."
        from drafts.tasks import _run

        _run(task.pk)
    prompt = complete.call_args[0][0]
    assert "Sei besonders kurz." in prompt
    assert "Zusätzliche Anweisungen für diese Antwort:" in prompt
