"""
Identification of requests and pairing of requests with replies.

Pure heuristics, no LLM. The archive's folder structure is only an
indicative signal; a request is identified by content first.
"""

import fnmatch
import logging
import re
from datetime import timedelta
from email.utils import parseaddr

from .loader import normalize_subject

logger = logging.getLogger(__name__)

CRITERIA = ("keyword", "domain", "folder")

DATE_WINDOW = timedelta(days=3)


def sender_domain(sender):
    address = parseaddr(sender or "")[1].lower()
    if "@" not in address:
        return ""
    return address.rsplit("@", 1)[1]


def mentions_type(text, request_type):
    lowered = (text or "").lower()
    needles = [request_type["name"].lower()]
    needles += [k.lower() for k in request_type.get("subject_keywords", [])]
    for needle in needles:
        if needle and needle in lowered:
            return True
    return True if not request_type.get("subject_keywords") and request_type["name"].lower() in lowered else False


def folder_matches(folder, patterns):
    if not folder or not patterns:
        return False
    lowered = folder.lower().replace("\\", "/")
    parts = lowered.strip("/").split("/")
    for pattern in patterns:
        p = (pattern or "").lower().replace("\\", "/").strip("/")
        if not p:
            continue
        if any(fnmatch.fnmatch(part, p) for part in parts):
            return True
        if fnmatch.fnmatch(lowered.strip("/"), p) or fnmatch.fnmatch(
            lowered.strip("/"), f"*/{p}"
        ):
            return True
    return False


def identify_request_type(mail, request_types):
    """Return (type key, criterion) for a mail, or (None, None).

    First match wins, in configuration order; later matches are
    ambiguous and reported by the caller.
    """
    subject = (mail.subject or "").lower()
    body = (mail.body or "").lower()
    folder = (mail.folder or "").lower()
    domain = sender_domain(mail.sender)

    matches = []
    for rt in request_types:
        key = rt.get("key")
        if not key:
            continue
        keywords = [k.lower() for k in rt.get("subject_keywords", []) if k]
        if any(k in subject for k in keywords):
            matches.append((key, "keyword"))
            continue
        domains = [d.lower().lstrip("@") for d in rt.get("sender_domains", []) if d]
        if domain and domain in domains and mentions_type(
            f"{mail.subject}\n{mail.body}", rt
        ):
            matches.append((key, "domain"))
            continue
        if folder_matches(mail.folder or "", rt.get("folders", [])):
            matches.append((key, "folder"))
    if not matches:
        return None, None, []
    return matches[0][0], matches[0][1], matches[1:]


def referenced_message_ids(mail):
    """All Message-IDs referenced by a mail (In-Reply-To + References)."""
    ids = []
    for header in (mail.in_reply_to, mail.references):
        for token in re.findall(r"<[^<>]+>", header or ""):
            if token not in ids:
                ids.append(token)
    return ids


def pair_request_with_replies(request, outgoing_mails):
    """Pair one identified request with its replies.

    Returns (primary_reply, replies, match_type): primary is the first
    chronological reply; `in_reply_to` when referenced, else the
    subject + ±3-day-window heuristic (`heuristic`).
    """
    request_id = request.message_id
    referenced = []
    if request_id:
        for mail in outgoing_mails:
            if request_id and request_id in referenced_message_ids(mail):
                referenced.append(mail)
    if referenced:
        referenced.sort(key=lambda m: (m.date is None, m.date))
        return referenced[0], referenced, "in_reply_to"

    if request.date is None:
        return None, [], "in_reply_to"
    normalized = normalize_subject(request.subject).lower()
    if not normalized:
        return None, [], "in_reply_to"
    window = [
        m
        for m in outgoing_mails
        if m.date is not None
        and abs(m.date - request.date) <= DATE_WINDOW
        and normalize_subject(m.subject).lower() == normalized
    ]
    if not window:
        return None, [], "in_reply_to"
    window.sort(key=lambda m: (m.date is None, m.date))
    return window[0], window, "heuristic"
