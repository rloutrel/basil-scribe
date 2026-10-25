"""LLM answer parsing: strict JSON, fenced blocks, non-JSON tolerance."""

from core.llm import parse_json_answer


def test_plain_json():
    assert parse_json_answer('{"category": "confirm_end"}') == {
        "category": "confirm_end"
    }


def test_json_in_code_fence():
    text = 'Here you go:\n```json\n{"category": "acknowledge_receipt"}\n```'
    assert parse_json_answer(text) == {"category": "acknowledge_receipt"}


def test_json_embedded_in_prose():
    text = 'Sure! {"category": "followup_question"} hope that helps.'
    assert parse_json_answer(text) == {"category": "followup_question"}


def test_non_json_regex_fallback():
    assert parse_json_answer("category: confirm_end") == {}
    assert parse_json_answer('"category": "confirm_end"') == {
        "category": "confirm_end"
    }


def test_invalid_and_empty():
    assert parse_json_answer("") == {}
    assert parse_json_answer("no category here") == {}
    assert parse_json_answer("[1, 2, 3]") == {}
