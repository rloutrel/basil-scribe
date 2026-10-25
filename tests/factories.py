"""Shared factories for tests; no external call is ever made."""

from datetime import datetime, timezone as dt_timezone
from email.message import EmailMessage
from email.utils import format_datetime

from profiles.models import Profile

PROFILE_A_REQUEST_TYPES = [
    {
        "key": "resignation",
        "name": "Kündigung der Mitgliedschaft",
        "subject_keywords": ["kündigung"],
        "sender_domains": ["fk-roro.de"],
        "folders": ["Kündigung_*"],
        "answer_categories": ["acknowledge_receipt", "confirm_end", "other"],
    },
    {
        "key": "application",
        "name": "Aufnahmeantrag",
        "subject_keywords": ["aufnahme", "beitritt"],
        "sender_domains": [],
        "folders": [],
        "answer_categories": ["acknowledge_receipt", "other"],
    },
]

PROFILE_B_REQUEST_TYPES = [
    {
        "key": "quote",
        "name": "Demande de devis",
        "subject_keywords": ["devis"],
        "sender_domains": [],
        "folders": [],
        "answer_categories": ["acknowledge_receipt", "other"],
    },
]


def make_profile(name="fk-roro", language="de", mail_source="fk-roro",
                 request_types=None, display_name=None, **extra):
    return Profile.objects.create(
        name=name,
        display_name=display_name or name,
        filename=f"{name}.yaml",
        language=language,
        mail_source=mail_source,
        organization_name="Förderkreis e.V.",
        greeting="Sie",
        signature="Mit freundlichen Grüßen\nDer Vorstand",
        rules="Die Mitgliedschaft endet zum Ende des Kalenderjahres.",
        role_prompt="Du bist ein Vorstandsmitglied.",
        temperature=0.5,
        request_types=(
            request_types
            if request_types is not None
            else [dict(rt) for rt in PROFILE_A_REQUEST_TYPES]
        ),
        **extra,
    )


def make_eml(tmp_path, name, subject, sender, body, date=None,
             message_id=None, in_reply_to=None, html=False,
             encoding="utf-8", folder="Inbox"):
    """Write one .eml file; return its bytes."""
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = "office@example.org"
    if message_id:
        msg["Message-ID"] = message_id
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
        msg["References"] = in_reply_to
    if date:
        msg["Date"] = format_datetime(
            datetime.fromisoformat(date).replace(tzinfo=dt_timezone.utc)
        )
    if html:
        msg.set_content(f"<html><body><p>{body}</p></body></html>", subtype="html")
    else:
        msg.set_content(body)
    raw = msg.as_bytes()
    if encoding != "utf-8":
        raw = msg.as_bytes(policy=__import__("email").policy.compat32)
        raw = raw.replace(b"Content-Type: text/plain; charset=\"utf-8\"",
                          b"Content-Type: text/plain; charset=\"iso-8859-1\"")
    target = tmp_path / folder
    target.mkdir(parents=True, exist_ok=True)
    (target / name).write_bytes(raw)
    return raw
