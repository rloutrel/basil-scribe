"""
Generation of reply drafts (step 3 and the UI side of step 4).

The draft always stays editable; nothing is ever sent automatically
(Basil rule: any reply to a third party requires human validation).
"""

import logging

from core import embeddings, kontext, llm
from precedents.index import cosine_top_k
from precedents.models import Precedent
from precedents.prompts import generation_prompt

logger = logging.getLogger(__name__)

TOP_K = 3
REQUEST_SUMMARY_MAX = 800


def similar_precedents(profile, request_type, request_text, exclude_ids=()):
    """Top-k precedents of the same profile and the same request type."""
    candidate_rows = list(
        Precedent.objects.filter(
            profile=profile, request_type=request_type
        )
        .exclude(embedding__isnull=True)
        .values_list("id", "embedding")
    )
    query = embeddings.embed(request_text)
    top = cosine_top_k(query, candidate_rows, k=TOP_K, exclude_ids=exclude_ids)
    precedents = {
        p.id: p
        for p in Precedent.objects.filter(id__in=[cid for cid, _score in top])
    }
    return [precedents[cid] for cid, _score in top if cid in precedents]


def precedent_blocks(precedents, request_type_name=""):
    """Render precedents as few-shot blocks (summaries, not full mails)."""
    blocks = []
    for p in precedents:
        request = p.request_mail
        summary = (request.body or request.subject or "").strip()
        if len(summary) > REQUEST_SUMMARY_MAX:
            summary = summary[:REQUEST_SUMMARY_MAX] + "…"
        header = request.subject or request_type_name
        blocks.append(
            {
                "id": p.id,
                "request": (f"[{header}]\n{summary}" if header else summary),
                "reply": (p.reply_mail.body or "").strip(),
            }
        )
    return blocks


def generate_draft(
    profile,
    request_type,
    request_text,
    recipient_name="",
    request_date="",
    exclude_precedent_ids=(),
):
    """Generate one reply draft; returns (draft_text, [precedent dicts]).

    Never blocks on context: the context seam returns an empty list in
    v1 and failures are swallowed.
    """
    rt = profile.request_type(request_type)
    if rt is None:
        raise ValueError("Unknown request type: %s" % request_type)

    precedents = similar_precedents(
        profile, request_type, request_text, exclude_ids=exclude_precedent_ids
    )
    blocks = precedent_blocks(precedents, rt["name"])
    try:
        context_source = kontext.get_context_source(profile)
        context_items = context_source.get_context(
            request_text, profile, request_type
        )
    except Exception:
        logger.exception("Context source failed; generating without context")
        context_items = []

    prompt = generation_prompt(
        profile_language=profile.language,
        role_prompt=profile.role_prompt,
        organization_rules=profile.rules,
        request_text=request_text,
        precedents=blocks,
        greeting=profile.greeting,
        signature=profile.signature,
        recipient_name=recipient_name,
        request_date=request_date,
        context_items=context_items,
    )
    draft_text = llm.complete(prompt, temperature=profile.temperature)
    return draft_text, [
        {
            "id": p.id,
            "request_subject": p.request_mail.subject,
            "reply_body": (p.reply_mail.body or "").strip(),
            "answer_category": p.answer_category,
        }
        for p in precedents
    ]
