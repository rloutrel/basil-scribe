"""Prompt assembly: block order, languages, and the context seam."""

from core.kontext import NullContext, get_context_source
from precedents.prompts import classification_prompt, generation_prompt


def test_generation_prompt_block_order_de():
    prompt = generation_prompt(
        profile_language="de",
        role_prompt="Du bist Vorstand.",
        organization_rules="Regel A.",
        request_text="Ich kündige.",
        precedents=[
            {"request": "Frühere Kündigung", "reply": "Sehr geehrte…"}
        ],
        greeting="Sie",
        signature="Mit freundlichen Grüßen",
        recipient_name="Herr Müller",
        request_date="2026-02-01",
    )
    assert prompt.index("Du bist Vorstand.") < prompt.index("Regel A.")
    assert prompt.index("Regel A.") < prompt.index("Ich kündige.")
    assert prompt.index("Ich kündige.") < prompt.index("Ähnlicher Fall 1")
    assert prompt.index("Ähnlicher Fall 1") < prompt.index("Mit freundlichen Grüßen")
    assert "Herr Müller" in prompt
    assert "Antworte auf Deutsch." in prompt


def test_generation_prompt_fr_and_context_block():
    prompt = generation_prompt(
        profile_language="fr",
        role_prompt="Tu es président.",
        organization_rules="Règle A.",
        request_text="Je démissionne.",
        precedents=[],
        greeting="vous",
        signature="Cordialement",
        context_items=["Fait historique"],
    )
    assert "Rédige une réponse complète" in prompt
    assert "Contexte pertinent" in prompt
    assert "Fait historique" in prompt
    assert "Cas similaire" not in prompt


def test_generation_prompt_no_rules_no_context():
    prompt = generation_prompt(
        profile_language="en",
        role_prompt="You are the chair.",
        organization_rules="",
        request_text="I resign.",
        precedents=[],
        greeting="you",
        signature="Regards",
    )
    assert "Organization rules" not in prompt
    assert "Relevant context" not in prompt
    assert "Similar case" not in prompt


def test_classification_prompt_contains_categories_and_fewshot():
    prompt = classification_prompt(
        profile_language="de",
        type_name="Kündigung",
        categories=["acknowledge_receipt", "confirm_end"],
        request_subject="Kündigung",
        request_body="Ich kündige.",
        reply_body="Erhalten.",
    )
    assert "acknowledge_receipt" in prompt
    assert "confirm_end" in prompt
    assert '{"category"' in prompt
    assert "Ich kündige." in prompt
    assert "Erhalten." in prompt


def test_null_context_returns_empty_and_never_blocks():
    source = get_context_source(None)
    assert isinstance(source, NullContext)
    assert source.get_context("text", None, "x") == []
    profile = type("P", (), {"context_enabled": True, "name": "p"})()
    assert isinstance(get_context_source(profile), NullContext)
