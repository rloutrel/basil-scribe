"""
Extraction of precedents from the mail archive (step 1).

`build_precedents` scans MAIL_EXPORT_ROOT/<mail_source>/, identifies
requests per profile request type, pairs them with the replies really
sent, embeds request bodies and stores `Precedent` rows. Idempotent:
the dedup key is sha256(request Message-ID + reply date + profile).
"""

import hashlib
import logging
from collections import Counter
from pathlib import Path

from django.conf import settings
from django.utils import timezone

from core import embeddings

from . import loader, matching
from .models import ArchiveMail, ExtractionReport, Precedent

logger = logging.getLogger(__name__)


def dedup_key(profile_id, request_message_id, reply_date):
    raw = f"{profile_id}|{request_message_id}|{reply_date}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def mail_source_root(profile):
    return Path(settings.MAIL_EXPORT_ROOT) / profile.mail_source


def build_precedents(profile, rebuild=False, progress=None):
    """Run the full extraction for one profile; return the report.

    The archive rows are a local cache of a read-only source, so every
    run rebuilds them: re-running is idempotent (no duplicates), with
    or without --rebuild.
    """
    ArchiveMail.objects.filter(profile=profile).delete()
    Precedent.objects.filter(profile=profile).delete()

    root = mail_source_root(profile)
    paths = loader.discover_eml_files(root)
    mails = []
    parsed = skipped = 0
    for i, path in enumerate(paths):
        data = loader.parse_eml(path)
        if data is None or not (data["subject"] or data["body"]):
            skipped += 1
            continue
        mail = ArchiveMail(profile=profile, **data)
        mails.append(mail)
        parsed += 1
        if progress:
            progress(i + 1, len(paths), str(path))
    ArchiveMail.objects.bulk_create(mails, batch_size=500)

    request_types = [
        rt for rt in profile.request_types if rt.get("key")
    ]
    identified = []  # (mail, type key, criterion)
    ambiguous = 0
    per_type = Counter()
    per_criterion = Counter()
    for mail in mails:
        if mail.is_outgoing:
            continue
        key, criterion, _ambiguities = matching.identify_request_type(
            mail, request_types
        )
        if key is None:
            continue
        ambiguous += len(_ambiguities)
        identified.append((mail, key, criterion))
        per_type[key] += 1
        per_criterion[criterion] += 1

    outgoing = [m for m in mails if m.is_outgoing]

    pairs = []
    unanswered = 0
    heuristic = 0
    by_id = {m.message_id: m for m in outgoing if m.message_id}
    for mail, key, criterion in identified:
        primary, replies, match_type = matching.pair_request_with_replies(
            mail, outgoing
        )
        if primary is None:
            unanswered += 1
            continue
        if match_type == "heuristic":
            heuristic += 1
        for reply in replies:
            pairs.append((mail, reply, key, criterion, match_type, reply is primary))

    unmatched_replies = len(outgoing) - len({p[1].pk for p in pairs if p[1].pk})

    stored = 0
    for request_mail, reply_mail, key, criterion, match_type, _primary in pairs:
        key_hash = dedup_key(
            profile.id, request_mail.message_id, reply_mail.date
        )
        embedding = embeddings.embed(request_mail.body or request_mail.subject or " ")
        Precedent.objects.update_or_create(
            dedup_key=key_hash,
            defaults={
                "profile": profile,
                "request_type": key,
                "request_mail": request_mail,
                "reply_mail": reply_mail,
                "match_source": criterion,
                "match_type": match_type,
                "embedding": embedding,
            },
        )
        stored += 1

    report = ExtractionReport.objects.create(
        profile=profile,
        rebuilt=rebuild,
        mails_parsed=parsed,
        mails_skipped=skipped,
        requests_identified=len(identified),
        pairs_matched=len(pairs),
        unanswered_requests=unanswered,
        heuristic_matches=heuristic,
        unmatched_replies=unmatched_replies,
        ambiguous_matches=ambiguous,
        per_type=dict(per_type),
        per_criterion=dict(per_criterion),
    )
    logger.info(
        "build_precedents(%s): parsed=%d requests=%d pairs=%d heuristic=%d "
        "unanswered=%d ambiguous=%d",
        profile.name,
        parsed,
        len(identified),
        len(pairs),
        heuristic,
        unanswered,
        ambiguous,
    )
    return report


def recent_extraction_summary(profile):
    """Small summary of the last extraction, for the home page."""
    report = profile.extraction_reports.first()
    if report is None:
        return None
    return {
        "created_at": report.created_at,
        "mails_parsed": report.mails_parsed,
        "requests_identified": report.requests_identified,
        "pairs_matched": report.pairs_matched,
        "heuristic_matches": report.heuristic_matches,
    }


def add_precedent_from_draft(draft):
    """Insert an accepted draft (request, final text) as a new precedent.

    The tool improves with use: accepted drafts become candidates for
    few-shot examples, within the same profile and request type only.
    """
    root = mail_source_root(draft.profile)
    now = timezone.now()
    request_mail = ArchiveMail.objects.create(
        profile=draft.profile,
        source_path="drafts/%d" % draft.pk,
        folder="Drafts",
        message_id="<draft-%d-request@basil-scribe>" % draft.pk,
        sender=draft.recipient_name or "",
        recipient=draft.profile.organization_name,
        subject="Draft %d" % draft.pk,
        date=draft.created_at or now,
        body=draft.request_text,
        is_outgoing=False,
    )
    reply_mail = ArchiveMail.objects.create(
        profile=draft.profile,
        source_path="drafts/%d" % draft.pk,
        folder="Drafts",
        message_id="<draft-%d-reply@basil-scribe>" % draft.pk,
        in_reply_to=request_mail.message_id,
        sender=draft.profile.organization_name,
        recipient=draft.recipient_name or "",
        subject="Re: Draft %d" % draft.pk,
        date=now,
        body=draft.final_text,
        is_outgoing=True,
    )
    embedding = embeddings.embed(draft.request_text)
    precedent = Precedent(
        profile=draft.profile,
        request_type=draft.request_type,
        request_mail=request_mail,
        reply_mail=reply_mail,
        match_source="keyword",
        match_type="in_reply_to",
        embedding=embedding,
        dedup_key=dedup_key(
            draft.profile.id, request_mail.message_id, reply_mail.date
        ),
    )
    precedent.save()
    draft.added_as_precedent = True
    draft.save(update_fields=["added_as_precedent"])
    return precedent
