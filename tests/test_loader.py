"""Parsing of .eml files: fixtures cover In-Reply-To, no reference,
HTML-only bodies and ISO-8859-1 encoding."""

from datetime import datetime, timezone
from email import policy
from email.message import EmailMessage
from email.utils import format_datetime

import pytest

from precedents.loader import (
    discover_eml_files,
    html_to_text,
    normalize_subject,
    parse_eml,
)


def _write(path, msg):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(msg.as_bytes())


def _msg(subject, body, **headers):
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = headers.get("From", "alice@example.com")
    msg["To"] = "office@example.org"
    for key in ("Message-ID", "In-Reply-To", "References"):
        if headers.get(key):
            msg[key] = headers[key]
    msg["Date"] = format_datetime(
        datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)
    )
    msg.set_content(body)
    return msg


def test_parse_basic_with_in_reply_to(tmp_path):
    _write(
        tmp_path / "Inbox" / "a.eml",
        _msg(
            "Kündigung der Mitgliedschaft",
            "Ich kündige zum Jahresende.",
            **{
                "Message-ID": "<req-1@example.com>",
                "In-Reply-To": "<other@example.com>",
            },
        ),
    )
    data = parse_eml(tmp_path / "Inbox" / "a.eml")
    assert data["message_id"] == "<req-1@example.com>"
    assert data["in_reply_to"] == "<other@example.com>"
    assert data["subject"] == "Kündigung der Mitgliedschaft"
    assert "kündige" in data["body"]
    assert data["date"] is not None
    assert data["is_outgoing"] is True  # has In-Reply-To


def test_parse_no_reference_is_incoming(tmp_path):
    _write(
        tmp_path / "Inbox" / "b.eml",
        _msg(
            "Frage",
            "Hallo",
            **{"Message-ID": "<req-2@example.com>"},
        ),
    )
    data = parse_eml(tmp_path / "Inbox" / "b.eml")
    assert data["in_reply_to"] == ""
    assert data["is_outgoing"] is False


def test_parse_html_only_body(tmp_path):
    msg = EmailMessage()
    msg["Subject"] = "HTML mail"
    msg["From"] = "x@example.com"
    msg["Date"] = format_datetime(datetime(2026, 2, 1, tzinfo=timezone.utc))
    msg.set_content(
        "<html><body><p>Hallo <b>Welt</b></p><p>Zweite Zeile</p></body></html>",
        subtype="html",
    )
    _write(tmp_path / "Inbox" / "c.eml", msg)
    data = parse_eml(tmp_path / "Inbox" / "c.eml")
    assert "Hallo Welt" in data["body"]
    assert "Zweite Zeile" in data["body"]
    assert "<p>" not in data["body"]


def test_parse_iso_8859_1(tmp_path):
    raw = (
        "From: x@example.com\r\n"
        "To: y@example.com\r\n"
        "Subject: =?iso-8859-1?q?K=FCndigung?=\r\n"
        "Message-ID: <iso@example.com>\r\n"
        "Date: Mon, 16 Feb 2026 10:00:00 +0000\r\n"
        "MIME-Version: 1.0\r\n"
        'Content-Type: text/plain; charset="iso-8859-1"\r\n'
        "Content-Transfer-Encoding: 8bit\r\n"
        "\r\n"
        "Ich k\xfcndige meine Mitgliedschaft.\r\n"
    ).encode("iso-8859-1")
    path = tmp_path / "Inbox" / "d.eml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    data = parse_eml(path)
    assert "Kündigung" in data["subject"]
    assert "kündige" in data["body"]


def test_parse_unreadable_file(tmp_path):
    assert parse_eml(tmp_path / "missing.eml") is None


def test_normalize_subject_strips_reply_prefixes():
    assert normalize_subject("Re: Kündigung") == normalize_subject("Kündigung")
    assert normalize_subject("AW: Frage") == normalize_subject("Frage")
    assert normalize_subject("Antw: Frage") == normalize_subject("Frage")
    assert normalize_subject("Frage") != normalize_subject("Andere")


def test_discover_eml_recursive_and_case_insensitive(tmp_path):
    (tmp_path / "Sent").mkdir(parents=True)
    (tmp_path / "Sent" / "x.eml").write_bytes(b"a")
    (tmp_path / "Archive" / "Sub").mkdir(parents=True)
    (tmp_path / "Archive" / "Sub" / "y.EML").write_bytes(b"a")
    (tmp_path / "Archive" / "Sub" / "z.txt").write_bytes(b"a")
    found = {p.name for p in discover_eml_files(tmp_path)}
    assert found == {"x.eml", "y.EML"}
    assert discover_eml_files(tmp_path / "nope") == []


def test_html_to_text_minimal():
    assert "line" in html_to_text("<p>line</p>")
    assert "a b" in html_to_text("a&nbsp;b")
    assert "script content" not in html_to_text(
        "<script>script content</script>ok"
    )
