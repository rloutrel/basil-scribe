"""Identification heuristics and request/reply pairing."""

from datetime import datetime, timezone
from types import SimpleNamespace

from precedents.matching import (
    folder_matches,
    identify_request_type,
    pair_request_with_replies,
)


def mail(subject="Hello", sender="a@example.com", body="", folder="Inbox",
         date=None, message_id="", in_reply_to="", references=""):
    return SimpleNamespace(
        subject=subject,
        sender=sender,
        body=body,
        folder=folder,
        date=date,
        message_id=message_id,
        in_reply_to=in_reply_to,
        references=references,
    )


REQUEST_TYPES = [
    {
        "key": "resignation",
        "name": "Kündigung",
        "subject_keywords": ["kündigung"],
        "sender_domains": ["fk-roro.de"],
        "folders": ["Kündigung_*"],
    },
    {
        "key": "application",
        "name": "Aufnahmeantrag",
        "subject_keywords": ["aufnahme"],
        "sender_domains": [],
        "folders": [],
    },
]


def test_keyword_match_wins():
    key, criterion, ambiguities = identify_request_type(
        mail(subject="Kündigung der Mitgliedschaft"), REQUEST_TYPES
    )
    assert (key, criterion) == ("resignation", "keyword")
    assert ambiguities == []


def test_domain_with_type_mention_in_body():
    key, criterion, _ = identify_request_type(
        mail(subject="Info", sender="vorstand@fk-roro.de",
             body="Es geht um die Kündigung."),
        REQUEST_TYPES,
    )
    assert (key, criterion) == ("resignation", "domain")


def test_domain_without_mention_no_match():
    key, criterion, _ = identify_request_type(
        mail(subject="Info", sender="vorstand@fk-roro.de", body="Sonstiges"),
        REQUEST_TYPES,
    )
    assert key is None


def test_folder_signal_only():
    key, criterion, _ = identify_request_type(
        mail(subject="Etwas", sender="x@example.com",
             folder="Kündigung_2026"),
        REQUEST_TYPES,
    )
    assert (key, criterion) == ("resignation", "folder")


def test_folder_glob_matches_part():
    assert folder_matches("Kündigung_2026", ["Kündigung_*"])
    assert folder_matches("Archive/Kündigung_alt", ["Kündigung_*"])
    assert not folder_matches("Inbox", ["Kündigung_*"])
    assert not folder_matches("", ["Kündigung_*"])
    assert not folder_matches("Kündigung", ["Kündigung_*"])


def test_first_type_wins_and_ambiguity_reported():
    types = [
        {"key": "a", "name": "Aufnahme", "subject_keywords": ["mitgliedschaft"],
         "sender_domains": [], "folders": []},
        {"key": "b", "name": "Kündigung", "subject_keywords": ["mitgliedschaft"],
         "sender_domains": [], "folders": []},
    ]
    key, criterion, ambiguities = identify_request_type(
        mail(subject="Mitgliedschaft"), types
    )
    assert key == "a"
    assert len(ambiguities) == 1
    assert ambiguities[0][0] == "b"


def test_pairing_by_in_reply_to():
    request = mail(subject="Kündigung", message_id="<r1@x>", date=datetime(
        2026, 1, 10, tzinfo=timezone.utc))
    reply = mail(subject="Re: Kündigung", folder="Sent",
                 date=datetime(2026, 1, 11, tzinfo=timezone.utc),
                 in_reply_to="<r1@x>")
    primary, replies, match_type = pair_request_with_replies(
        request, [reply]
    )
    assert primary is reply
    assert match_type == "in_reply_to"
    assert replies == [reply]


def test_pairing_keeps_all_replies_first_chronological():
    request = mail(subject="Kündigung", message_id="<r1@x>", date=datetime(
        2026, 1, 10, tzinfo=timezone.utc))
    later = mail(subject="Re: Kündigung", folder="Sent",
                 date=datetime(2026, 1, 12, tzinfo=timezone.utc),
                 in_reply_to="<r1@x>")
    earlier = mail(subject="Re: Kündigung", folder="Sent",
                   date=datetime(2026, 1, 11, tzinfo=timezone.utc),
                   in_reply_to="<r1@x>")
    primary, replies, match_type = pair_request_with_replies(
        request, [later, earlier]
    )
    assert primary is earlier
    assert len(replies) == 2
    assert {id(r) for r in replies} == {id(earlier), id(later)}
    assert match_type == "in_reply_to"


def test_pairing_heuristic_subject_and_window():
    request = mail(subject="Kündigung", message_id="<r2@x>", date=datetime(
        2026, 1, 10, tzinfo=timezone.utc))
    within = mail(subject="AW: Kündigung", folder="Sent",
                  date=datetime(2026, 1, 12, tzinfo=timezone.utc))
    too_late = mail(subject="Re: Kündigung", folder="Sent",
                    date=datetime(2026, 1, 20, tzinfo=timezone.utc))
    primary, replies, match_type = pair_request_with_replies(
        request, [too_late, within]
    )
    assert primary is within
    assert match_type == "heuristic"


def test_pairing_heuristic_boundary_three_days():
    request = mail(subject="Kündigung", message_id="<r3@x>", date=datetime(
        2026, 1, 10, tzinfo=timezone.utc))
    edge = mail(subject="Re: Kündigung", folder="Sent",
                date=datetime(2026, 1, 13, tzinfo=timezone.utc))
    beyond = mail(subject="Re: Kündigung", folder="Sent",
                  date=datetime(2026, 1, 14, tzinfo=timezone.utc))
    primary, _, match_type = pair_request_with_replies(request, [beyond, edge])
    assert primary is edge
    primary, _, _ = pair_request_with_replies(request, [beyond])
    assert primary is None


def test_pairing_no_reply():
    request = mail(subject="Kündigung", message_id="<r4@x>", date=datetime(
        2026, 1, 10, tzinfo=timezone.utc))
    assert pair_request_with_replies(request, []) == (None, [], "in_reply_to")
