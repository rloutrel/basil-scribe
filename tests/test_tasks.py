"""The async generation task machinery."""

from unittest import mock

import pytest

from drafts.models import GenerationTask
from drafts.tasks import _run, submit

from .factories import make_profile


@pytest.fixture
def profile(db):
    return make_profile()


def test_submit_creates_queued_task(profile):
    task = submit(
        profile,
        "resignation",
        "Ich kündige.",
        recipient_name="Herr X",
        request_date="2026-02-01",
        exclude_precedent_ids=["7"],
    )
    task.refresh_from_db()
    assert task.status == "queued"
    assert task.request_type == "resignation"
    assert task.recipient_name == "Herr X"
    assert task.exclude_precedent_ids == ["7"]


def test_run_records_progress_and_result(profile):
    labels = []

    def fake_generate(*args, progress=None, **kwargs):
        if progress:
            progress("step one")
            progress("step two")
        return "Antwort", [{"id": 1, "request_subject": "s", "reply_body": "r"}]

    task = submit(profile, "resignation", "Ich kündige.")
    with mock.patch(
        "drafts.tasks.generate_draft", side_effect=fake_generate
    ) as generate:
        _run(task.pk)
    task.refresh_from_db()
    assert task.status == "done"
    assert task.generated_text == "Antwort"
    assert task.precedents_used[0]["reply_body"] == "r"
    assert task.error == ""
    assert generate.call_args.kwargs["progress"] is not None


def test_run_catches_any_exception(profile):
    task = submit(profile, "resignation", "Ich kündige.")
    with mock.patch(
        "drafts.tasks.generate_draft",
        side_effect=RuntimeError("boom"),
    ):
        _run(task.pk)
    task.refresh_from_db()
    assert task.status == "failed"
    assert "boom" in task.error


def test_run_reports_llm_errors(profile):
    from core.llm import LLMError

    task = submit(profile, "resignation", "Ich kündige.")
    with mock.patch(
        "drafts.tasks.generate_draft",
        side_effect=LLMError("connection refused"),
    ):
        _run(task.pk)
    task.refresh_from_db()
    assert task.status == "failed"
    assert "connection refused" in task.error


def test_run_scoped_to_profile_task(profile, db):
    other = make_profile(name="corp")
    task = submit(profile, "resignation", "Ich kündige.")
    with mock.patch("drafts.tasks.generate_draft") as generate:
        _run(task.pk)
    assert GenerationTask.objects.filter(profile=other).count() == 0
    assert generate.called
