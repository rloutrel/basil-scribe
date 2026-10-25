"""Actionable LLM errors: unconfigured or unknown model names."""

import sys
import types
from unittest import mock

import pytest

from core.llm import LLMError, complete


@pytest.fixture(autouse=True)
def fake_openai(monkeypatch):
    """Provide a stub openai module: never a real network client."""
    module = types.ModuleType("openai")
    module.OpenAI = mock.MagicMock()
    monkeypatch.setitem(sys.modules, "openai", module)


@pytest.mark.django_db
def test_missing_llm_model_setting_is_actionable(settings):
    settings.LLM_MODEL = ""
    with pytest.raises(LLMError) as exc_info:
        complete("hello")
    assert "LLM_MODEL is not configured" in str(exc_info.value)
    assert "ollama list" in str(exc_info.value)


@pytest.mark.django_db
def test_unknown_model_error_names_the_model(settings):
    settings.LLM_MODEL = "llama3.1:8b"

    class FakeNotFound(Exception):
        def __str__(self):
            return (
                "Error code: 404 - {'error': {'message': "
                "\"model 'llama3.1:8b' not found\"}}"
            )

    with mock.patch("openai.OpenAI") as client:
        instance = client.return_value
        instance.chat.completions.create.side_effect = FakeNotFound()
        with pytest.raises(LLMError) as exc_info:
            complete("hello")
    message = str(exc_info.value)
    assert "llama3.1:8b" in message
    assert "ollama list" in message
    assert "LLM_MODEL" in message
    assert "tag included" in message


@pytest.mark.django_db
def test_other_llm_errors_pass_through(settings):
    settings.LLM_MODEL = "llama3.1:latest"

    with mock.patch("openai.OpenAI") as client:
        instance = client.return_value
        instance.chat.completions.create.side_effect = RuntimeError("boom")
        with pytest.raises(LLMError) as exc_info:
            complete("hello")
    assert "boom" in str(exc_info.value)
