"""
LLM access seam.

In v1 the LLM is a local Ollama server reached through the OpenAI SDK.
This module and `core.embeddings` are the ONLY seams with
basil-chambellan, the future central broker for model access (local vs
remote, model per task, API tokens). Nothing else in the codebase may
call Ollama or the OpenAI SDK.
"""

import json
import logging
import re

from django.conf import settings

logger = logging.getLogger(__name__)


class LLMError(Exception):
    pass


def complete(prompt, temperature=0.7):
    """Run a single chat completion; return the assistant text."""
    try:
        from openai import OpenAI
    except ImportError:
        raise LLMError("openai is not installed")
    if not settings.LLM_MODEL:
        raise LLMError(
            "LLM_MODEL is not configured. Set it in .env to a model your "
            "Ollama serves (as shown by `ollama list`, tag included)."
        )
    try:
        client = OpenAI(base_url=settings.OLLAMA_BASE_URL, api_key="ollama")
        response = client.chat.completions.create(
            model=settings.LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=float(temperature),
        )
        return response.choices[0].message.content
    except Exception as exc:
        message = str(exc)
        if "not found" in message and settings.LLM_MODEL in message:
            raise LLMError(
                f"Model '{settings.LLM_MODEL}' is not served by your "
                "Ollama. Check `ollama list` and set LLM_MODEL in .env "
                "to the exact name, tag included (e.g. llama3.1:latest)."
            ) from exc
        logger.exception("LLM call failed")
        raise LLMError(message) from exc


JSON_BLOCK = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


def parse_json_answer(text):
    """Extract a dict from an LLM answer that should be JSON.

    Tolerant fallback: find the outermost braces. Returns an empty dict
    when nothing parses.
    """
    if not text:
        return {}
    candidate = text.strip()
    block = JSON_BLOCK.search(candidate)
    if block:
        candidate = block.group(1)
    try:
        result = json.loads(candidate)
        return result if isinstance(result, dict) else {}
    except (ValueError, TypeError):
        pass
    match = re.search(r"\{.*\}", candidate, re.DOTALL)
    if match:
        try:
            result = json.loads(match.group(0))
            return result if isinstance(result, dict) else {}
        except (ValueError, TypeError):
            pass
    match = re.search(r'"category"\s*:\s*"([^"]+)"', candidate)
    if match:
        return {"category": match.group(1)}
    return {}
