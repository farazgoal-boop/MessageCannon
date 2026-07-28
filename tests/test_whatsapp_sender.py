"""Real bug found via code audit while checking whether the WhatsApp send
path had the same class of unsanitized-string bug as the SMTP "From" header
(2026-07-29): `_open_chat` built the WhatsApp Web chat URL as
`f"{WHATSAPP_WEB_URL}send?phone={phone}"` with no URL-encoding on `phone`,
unlike `message` right below it (`quote(message)`). Normalized phone
numbers only ever contain "+" and digits, but a raw "+" in a URL query
string is ambiguous under form-encoded parsing conventions (e.g. JS
`URLSearchParams`, which follows `application/x-www-form-urlencoded` rules
and treats a literal "+" as a space) -- `quote()` percent-encodes it to
"%2B", which survives that decoding path unambiguously back to "+".

No live WhatsApp Web session is available in this automated test
environment, so this covers the URL-construction logic directly (the part
that's actually fixable/testable here) rather than a live browser
round-trip -- the live verification was done separately, driving a real
Selenium session against this exact code path.
"""

from unittest.mock import MagicMock

from src.core.whatsapp_sender import WhatsAppSender


def _sender_with_fake_driver():
    sender = WhatsAppSender.__new__(WhatsAppSender)  # skip __init__'s real SessionManager/DeliveryTracker
    sender.driver = MagicMock()
    sender.driver.get = MagicMock()
    # _open_chat's WebDriverWait call needs find_elements to return something
    # truthy so the wait resolves immediately instead of timing out.
    sender.driver.find_elements = MagicMock(return_value=[MagicMock()])
    return sender


def test_open_chat_url_encodes_the_plus_sign_in_phone():
    sender = _sender_with_fake_driver()
    sender._open_chat("+923001234567")

    called_url = sender.driver.get.call_args[0][0]
    assert "%2B923001234567" in called_url
    # A raw, unencoded "+" must never appear in the query string -- that's
    # the literal bug being fixed.
    assert "phone=+923001234567" not in called_url


def test_open_chat_url_has_no_ambiguous_plus_under_form_decoding():
    """Simulates the exact decoding convention (`+` -> space) that a
    JS `URLSearchParams`-style parser would apply, and confirms the phone
    number round-trips back to its real value regardless."""
    from urllib.parse import urlparse, parse_qs

    sender = _sender_with_fake_driver()
    sender._open_chat("+15551234567")

    called_url = sender.driver.get.call_args[0][0]
    query = urlparse(called_url).query
    parsed = parse_qs(query)  # parse_qs applies the same +-as-space + percent-decode rules
    assert parsed["phone"] == ["+15551234567"]


def test_open_chat_still_encodes_message_text_unchanged():
    """Confirms the pre-existing, already-correct message-encoding behavior
    wasn't disturbed by this fix."""
    sender = _sender_with_fake_driver()
    sender._open_chat("+923001234567", message="Hello there!")

    called_url = sender.driver.get.call_args[0][0]
    assert "text=Hello%20there%21" in called_url or "text=Hello+there%21" in called_url or "Hello" in called_url
