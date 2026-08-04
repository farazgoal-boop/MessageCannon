"""Unit coverage for src/core/bounce_checker.py -- the pure RFC 3464 bounce
parser (tested against real, realistic MIME bounce messages, not just
hand-picked strings) and the IMAP host-guessing helper. The real, live IMAP
scan (check_for_bounces against a real inbox) is proven separately in a real
end-to-end test against the app's own real Gmail account, not here -- this
file only covers what's safe/fast to test without real network I/O:
message-level parsing, provider-mapping logic, and check_for_bounces'
own defensive contract via a mocked imaplib connection.
"""

import email
from unittest.mock import MagicMock, patch

from src.core import bounce_checker as bc


# A real, realistic Gmail-style RFC 3464 bounce (structured DSN part) --
# modeled directly on Gmail's actual bounce format.
GMAIL_STYLE_BOUNCE = """From: Mail Delivery Subsystem <mailer-daemon@googlemail.com>
To: sender@gmail.com
Subject: Delivery Status Notification (Failure)
Content-Type: multipart/report; report-type=delivery-status; boundary="b1"
MIME-Version: 1.0

--b1
Content-Type: text/plain; charset=UTF-8

** Address not found **

Your message wasn't delivered to bogus-mc-test@gmail.com because the address
couldn't be found, or is unable to receive mail.

--b1
Content-Type: message/delivery-status

Reporting-MTA: dns; googlemail.com

Final-Recipient: rfc822; bogus-mc-test@gmail.com
Action: failed
Status: 5.1.1
Diagnostic-Code: smtp; 550-5.1.1 The email account that you tried to reach does not exist.

--b1
Content-Type: message/rfc822

From: sender@gmail.com
To: bogus-mc-test@gmail.com
Subject: Original message

Body of the original message.

--b1--
"""

# A plain-text-only bounce (no structured DSN part) -- exercises the
# sender/subject heuristic + body address-scan fallback.
PLAIN_TEXT_BOUNCE = """From: postmaster@example-corp.com
To: sender@gmail.com
Subject: Undeliverable: Your message
Content-Type: text/plain; charset=UTF-8

This is an automatically generated message.

Delivery to the following recipient failed permanently:

     nobody-here@example-corp.com

Reason: 550 5.1.1 User unknown
"""

# A completely ordinary, real inbox message -- must never be misdetected as
# a bounce.
NORMAL_MESSAGE = """From: friend@example.com
To: sender@gmail.com
Subject: Hey, how's it going?
Content-Type: text/plain; charset=UTF-8

Just checking in, nothing important.
"""


def test_dsn_bounce_extracts_recipient_and_reason():
    msg = email.message_from_string(GMAIL_STYLE_BOUNCE)
    result = bc.parse_bounce_message(msg)
    assert result.is_bounce is True
    assert result.failed_recipients == {"bogus-mc-test@gmail.com"}
    assert "550" in result.reason and "5.1.1" in result.reason


def test_plain_text_bounce_falls_back_to_heuristic_and_body_scan():
    msg = email.message_from_string(PLAIN_TEXT_BOUNCE)
    result = bc.parse_bounce_message(msg)
    assert result.is_bounce is True
    assert "nobody-here@example-corp.com" in result.failed_recipients
    assert result.reason  # some non-empty reason, from subject fallback


def test_normal_message_is_never_flagged_a_bounce():
    msg = email.message_from_string(NORMAL_MESSAGE)
    result = bc.parse_bounce_message(msg)
    assert result.is_bounce is False
    assert result.failed_recipients == set()


def test_guess_imap_host_prefers_provider_name():
    assert bc.guess_imap_host("smtp.gmail.com", provider="Gmail") == ("imap.gmail.com", 993)
    assert bc.guess_imap_host("smtp-mail.outlook.com", provider="Outlook") == ("outlook.office365.com", 993)
    assert bc.guess_imap_host("smtp.mail.yahoo.com", provider="Yahoo") == ("imap.mail.yahoo.com", 993)


def test_guess_imap_host_falls_back_to_known_smtp_host_when_no_provider():
    assert bc.guess_imap_host("smtp.gmail.com") == ("imap.gmail.com", 993)


def test_guess_imap_host_generic_prefix_swap_for_unknown_custom_host():
    assert bc.guess_imap_host("smtp.mycompany.io") == ("imap.mycompany.io", 993)


def test_guess_imap_host_returns_none_when_nothing_can_be_guessed():
    assert bc.guess_imap_host("mail.totally-custom-server.net") is None
    assert bc.guess_imap_host("") is None


def test_check_for_bounces_returns_ok_empty_when_no_candidates():
    result = bc.check_for_bounces("imap.gmail.com", 993, "u", "p", candidate_emails=set())
    assert result.ok is True
    assert result.bounces == {}


def test_check_for_bounces_reports_connect_failure_without_raising():
    with patch("src.core.bounce_checker.imaplib.IMAP4_SSL", side_effect=OSError("no route to host")):
        result = bc.check_for_bounces(
            "imap.gmail.com", 993, "u", "p", candidate_emails={"a@test.dev"})
    assert result.ok is False
    assert "no route to host" in result.error


def test_check_for_bounces_reports_login_failure_without_raising():
    fake_conn = MagicMock()
    fake_conn.login.side_effect = __import__("imaplib").IMAP4.error("bad credentials")
    with patch("src.core.bounce_checker.imaplib.IMAP4_SSL", return_value=fake_conn):
        result = bc.check_for_bounces(
            "imap.gmail.com", 993, "u", "wrong-pass", candidate_emails={"a@test.dev"})
    assert result.ok is False
    assert "bad credentials" in result.error
    fake_conn.logout.assert_called_once()


def test_check_for_bounces_selects_inbox_readonly_and_never_deletes_or_flags():
    fake_conn = MagicMock()
    fake_conn.select.return_value = ("OK", [b"1"])
    fake_conn.search.return_value = ("OK", [b""])
    with patch("src.core.bounce_checker.imaplib.IMAP4_SSL", return_value=fake_conn):
        result = bc.check_for_bounces(
            "imap.gmail.com", 993, "u", "p", candidate_emails={"a@test.dev"})
    assert result.ok is True
    fake_conn.select.assert_called_once_with("INBOX", readonly=True)
    fake_conn.store.assert_not_called()
    fake_conn.expunge.assert_not_called()


def test_check_for_bounces_end_to_end_with_mocked_imap_finds_real_candidate_bounce():
    """Full flow with a mocked IMAP server (real network I/O is proven
    separately, live) -- search returns one message id, fetch returns the
    real Gmail-style bounce MIME above, and the reported bounce only
    includes the address that's actually in our candidate set."""
    fake_conn = MagicMock()
    fake_conn.select.return_value = ("OK", [b"1"])

    def fake_search(charset, criteria):
        if "mailer-daemon" in criteria:
            return ("OK", [b"42"])
        return ("OK", [b""])

    fake_conn.search.side_effect = fake_search
    fake_conn.fetch.return_value = ("OK", [(b"42 (RFC822 {123}", GMAIL_STYLE_BOUNCE.encode("utf-8"))])

    with patch("src.core.bounce_checker.imaplib.IMAP4_SSL", return_value=fake_conn):
        result = bc.check_for_bounces(
            "imap.gmail.com", 993, "u", "p",
            candidate_emails={"bogus-mc-test@gmail.com", "someone-else@gmail.com"})

    assert result.ok is True
    assert result.bounces == {"bogus-mc-test@gmail.com": "smtp; 550-5.1.1 The email account that you tried to reach does not exist."}
    assert "someone-else@gmail.com" not in result.bounces
    fake_conn.logout.assert_called_once()
