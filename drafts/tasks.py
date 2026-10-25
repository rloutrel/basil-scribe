"""
Asynchronous draft generation.

A generation can take minutes (embedding model load on first call, LLM
inference), which does not fit a plain HTTP request/response cycle.
`submit` queues a GenerationTask on a single-worker thread pool — the
embedding model is heavy and only ever needs one copy in memory — and
runs the generation with coarse progress updates the UI polls.
"""

import logging
import threading
from concurrent.futures import ThreadPoolExecutor

from django.utils.translation import gettext as _

from core.llm import LLMError
from profiles.middleware import activate_profile_language

from .generation import generate_draft
from .models import GenerationTask

logger = logging.getLogger(__name__)

_POOL = None
_POOL_LOCK = threading.Lock()


def start_pool():
    """Start the background pool (called once at app startup in
    production; tests leave it off and drive _run directly)."""
    global _POOL
    with _POOL_LOCK:
        if _POOL is None:
            _POOL = ThreadPoolExecutor(
                max_workers=1, thread_name_prefix="basil-scribe-gen"
            )
    return _POOL


def submit(profile, request_type, request_text, recipient_name="",
           request_date="", exclude_precedent_ids=()):
    """Create a queued task and start its execution in the background.

    The pool is lazily created; tests replace it with a no-op to keep
    execution synchronous and deterministic.
    """
    global _POOL
    task = GenerationTask.objects.create(
        profile=profile,
        request_type=request_type,
        request_text=request_text,
        recipient_name=recipient_name,
        request_date=request_date,
        exclude_precedent_ids=[str(i) for i in exclude_precedent_ids],
        status="queued",
    )
    if _POOL is not None:
        _POOL.submit(_run, task.pk)
    return task


def _update(task, **fields):
    for name, value in fields.items():
        setattr(task, name, value)
    task.save(update_fields=list(fields) + ["updated_at"])


def _run(task_id):
    """Worker body: run one generation, recording progress and outcome.

    Never raises: any failure is stored on the task so the UI can show
    an actionable message instead of a dead spinner.
    """
    task = GenerationTask.objects.select_related("profile").get(pk=task_id)
    profile = task.profile
    activate_profile_language(profile)
    try:
        _update(task, status="running",
                progress=_("Loading the embedding model…"))
        draft_text, precedents_used = generate_draft(
            profile,
            task.request_type,
            task.request_text,
            recipient_name=task.recipient_name,
            request_date=task.request_date,
            exclude_precedent_ids=task.exclude_precedent_ids,
            progress=lambda label: _update(task, progress=label),
        )
        _update(
            task,
            status="done",
            progress="",
            generated_text=draft_text,
            precedents_used=precedents_used,
        )
    except LLMError as exc:
        logger.exception("Generation task %s failed", task_id)
        _update(task, status="failed", progress="", error=str(exc))
    except Exception as exc:
        logger.exception("Generation task %s failed", task_id)
        _update(task, status="failed", progress="", error=str(exc))
