"""
Parsing of `.eml` archive files.

Uses only the standard library (`email`). The archive is mounted
read-only; this module never writes, moves or deletes anything.
"""

import email
import logging
import re
from datetime import datetime, timezone
from email import policy
from email.header import decode_header, make_header
from email.utils import getaddresses, parsedate_to_datetime
from pathlib import Path

logger = logging.getLogger(__name__)

REPLY_RE = re.compile(r"^\s*(re|aw|antw|antwort|sv)\s*:", re.IGNORECASE)
MSGID_RE = re.compile(r"<[^<>]+>")
FALLBACK_ENCODING = "ISO-8859-1"
SENT_FOLDER_PARTS = ("sent", "gesendet", "inbox/sent")


def decode_header_value(value):
    """Decode an RFC 2047 header into a unicode string."""
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value)))
    except Exception:
        return str(value)


def _message_from_bytes(raw):
    try:
        return email.message_from_bytes(raw, policy=policy.default)
    except Exception:
        return email.message_from_bytes(raw)


def parse_eml(path):
    """Parse one `.eml` file into a plain dict.

    Returns None when the file cannot be read or parsed at all.
    HTML-only bodies are converted to text. ISO-8859-1 (and other
    charsets) fall back gracefully.
    """
    path = Path(path)
    try:
        raw = path.read_bytes()
    except OSError:
        logger.warning("Unreadable archive file: %s", path)
        return None
    msg = _message_from_bytes(raw)
    if msg is None:
        return None

    body = _extract_body(msg)
    result = {
        "source_path": str(path),
        "folder": _folder_of(path),
        "message_id": _clean_msgid(decode_header_value(msg.get("Message-ID", ""))),
        "in_reply_to": _clean_msgid(
            decode_header_value(msg.get("In-Reply-To", ""))
        ),
        "references": decode_header_value(msg.get("References", "")),
        "sender": decode_header_value(msg.get("From", "")),
        "recipient": decode_header_value(msg.get("To", "")),
        "subject": decode_header_value(msg.get("Subject", "")),
        "date": _parse_date(msg.get("Date", "")),
        "body": body,
        "is_outgoing": _is_outgoing(path, msg),
    }
    return result


def _clean_msgid(value):
    match = MSGID_RE.search(value or "")
    return match.group(0) if match else (value or "").strip()


def _folder_of(path):
    return path.parent.name


def _parse_date(value):
    if not value:
        return None
    try:
        dt = parsedate_to_datetime(str(value))
    except (TypeError, ValueError):
        return None
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _decode_part(part):
    payload = part.get_content()
    if isinstance(payload, bytes):
        charset = part.get_content_charset() or FALLBACK_ENCODING
        try:
            return payload.decode(charset, errors="replace")
        except LookupError:
            return payload.decode(FALLBACK_ENCODING, errors="replace")
    return payload


def _extract_body(msg):
    plain = []
    html = []
    if msg.is_multipart():
        parts = msg.walk()
    else:
        parts = iter([msg])
    for part in parts:
        if part.is_multipart() or part.get_content_disposition() == "attachment":
            continue
        maintype = part.get_content_maintype()
        subtype = part.get_content_subtype()
        try:
            if maintype == "text" and subtype == "html":
                html.append(_decode_part(part))
            elif maintype == "text" and subtype == "plain":
                plain.append(_decode_part(part))
        except Exception:
            logger.debug("Undecodable part in %s", msg.get("Message-ID", "?"))
    if plain:
        return "\n".join(plain).strip()
    if html:
        return html_to_text("\n".join(html)).strip()
    try:
        fallback = msg.get_content()
    except Exception:
        return ""
    if isinstance(fallback, bytes):
        return fallback.decode(FALLBACK_ENCODING, errors="replace").strip()
    return str(fallback).strip()


def html_to_text(html):
    """Very small converter, good enough to index and display."""
    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", html)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</p>", "\n\n", text)
    text = re.sub(r"(?i)</div>", "\n", text)
    text = re.sub(r"(?i)</tr>", "\n", text)
    text = re.sub(r"(?i)</t[dh]>", "  ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = (
        text.replace("&nbsp;", " ")
        .replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", '"')
        .replace("&#39;", "'")
    )
    return re.sub(r"\n{3,}", "\n\n", re.sub(r"[ \t]+", " ", text)).strip()


def normalize_subject(subject):
    """Lowercased subject without reply prefixes, for pairing heuristics."""
    text = decode_header_value(subject or "").strip()
    while True:
        stripped = REPLY_RE.sub("", text, count=1)
        if stripped == text:
            break
        text = stripped.strip()
    return text.casefold()


def _is_outgoing(path, msg):
    """A reply candidate is a mail in a sent folder or one that references
    other mails (In-Reply-To/References) — it is a mail *we* sent."""
    folder = path.parent.name.lower()
    if folder in SENT_FOLDER_PARTS:
        return True
    in_reply_to = decode_header_value(msg.get("In-Reply-To", ""))
    references = decode_header_value(msg.get("References", ""))
    return bool(MSGID_RE.search(in_reply_to) or MSGID_RE.search(references))


def discover_eml_files(root):
    """Recursively yield every `.eml` under root (case-insensitive)."""
    root = Path(root)
    if not root.exists():
        return []
    return sorted(
        p for p in root.rglob("*") if p.is_file() and p.suffix.lower() == ".eml"
    )


def referenced_message_ids(msg):
    """Message-IDs referenced by a parsed message dict."""
    ids = []
    for header in (msg.get("in_reply_to", ""), msg.get("references", "")):
        for token in MSGID_RE.findall(header or ""):
            if token not in ids:
                ids.append(token)
    return ids
