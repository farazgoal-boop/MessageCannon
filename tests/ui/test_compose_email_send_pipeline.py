"""Compose → SMTP send pipeline (Compose reliability pass, P0/P2/P3).

What this locks in:

- The HTML that Card Creator / Import HTML produces reaches the SMTP wire
  UNMODIFIED except for {variable} substitution and the compliance footer —
  it is never flattened to plain text.
- The message is a real multipart/alternative carrying BOTH a text/plain
  part and the full text/html part (inline styles intact).
- The compliance opt-out line ("Reply STOP") is present in the actual sent
  bytes, in both parts (P3).
- opted-out AND previously-bounced contacts are excluded from the real
  recipient list (P3).
- "Send test to myself" builds and sends exactly one message the same way a
  real batch would, to the configured account, without creating a campaign
  row.
- The Recipients panel spells out who is excluded and why, and shows what
  the last run did (P2).

Uses a dedicated, module-scoped, fresh-DB MainWindow (same pattern as
test_email_visual_card_mode.py). smtplib.SMTP is replaced with an in-memory
fake — no real network.
"""

import time
import tkinter as tk

import pytest

from src.models import Contact


class _SynchronousThread:
    """Runs the target inline on the calling (main) thread. This harness
    drives the app via update() polling, not a real mainloop(), so a real
    background thread touching Tk (StringVar.get(), self.after()) raises
    "main thread is not in main loop" — same documented limitation worked
    around in test_ai_error_reporting.py / test_email_visual_card_mode.py.
    Only the concurrency is stubbed; the real send logic still runs."""

    def __init__(self, target=None, daemon=None, **_kwargs):
        self._target = target

    def start(self):
        if self._target:
            self._target()

    def is_alive(self):
        return False


def _pump(window, predicate=None, timeout_s: float = 3.0) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        window.update()
        if predicate is None or predicate():
            return True
        time.sleep(0.01)
    return bool(predicate and predicate())


CARD_HTML = (
    "<!DOCTYPE html><html><head><style>.card{background:#1a1a2e}</style></head>"
    "<body style=\"background:#111827\">"
    "<div class=\"card\" style=\"background:#1a1a2e;border-radius:20px\">"
    "<h1 style=\"color:#E2E8F0\">Hello {name}</h1>"
    "<a href=\"https://example.com\" style=\"background:#6366F1;color:#fff;"
    "padding:10px 18px;border-radius:8px;display:inline-block\">Buy Now</a>"
    "</div></body></html>"
)


class _FakeSMTP:
    sent = []

    def __init__(self, host, port, timeout=None):
        self.host = host

    def starttls(self, context=None):
        pass

    def login(self, user, password):
        self.user = user

    def sendmail(self, from_addr, to_addr, msg_string):
        _FakeSMTP.sent.append((from_addr, to_addr, msg_string))

    def quit(self):
        pass


def _close_any_toplevel(window) -> None:
    def walk(widget):
        for child in widget.children.values():
            if isinstance(child, tk.Toplevel):
                return child
            found = walk(child)
            if found:
                return found
        return None
    top = walk(window)
    if top is not None:
        top.destroy()


@pytest.fixture(scope="module")
def window(tmp_path_factory):
    from src.database import db_manager as db_manager_module

    mp = pytest.MonkeyPatch()
    fresh_db_path = str(tmp_path_factory.mktemp("send_pipeline") / "test.db")
    mp.setattr(db_manager_module, "get_database_path", lambda: fresh_db_path)
    db_manager_module.DatabaseManager._instance = None

    from src.ui.main_window import MainWindow

    win = MainWindow()
    _close_any_toplevel(win)
    win.update()
    win._show_view("Compose")
    win._compose_channel_var.set("Email")
    win._on_channel_switch("Email")
    win._em_host.set("smtp.test.dev")
    win._em_port.set("587")
    win._em_user.set("me@test.dev")
    win._em_pass.set("app-password")
    win._em_from_name.set("Test Sender")
    win._em_from_addr.set("me@test.dev")
    win._em_delay.set("0")
    win.email_warmup_enabled_var.set(False)
    win.jitter_var.set(False)
    win.update()
    try:
        yield win
    finally:
        try:
            if win.winfo_exists():
                win.destroy()
        except Exception:
            pass
        db_manager_module.DatabaseManager._instance = None
        mp.undo()


@pytest.fixture(autouse=True)
def _reset(window, monkeypatch):
    _FakeSMTP.sent = []
    monkeypatch.setattr("src.ui.main_window.smtplib.SMTP", _FakeSMTP)
    monkeypatch.setattr("src.ui.main_window.threading.Thread", _SynchronousThread)
    monkeypatch.setattr("src.ui.main_window.MainWindow._show_email_report",
                        lambda *a, **k: None)
    # Per-send delay is "0" in the module fixture, so the real time.sleep in
    # the send loop is already instant.
    if window._compose_card_mode:
        window._exit_email_card_mode()
    window.contacts = []
    window._em_send_thread = None
    window.update()
    yield
    _close_any_toplevel(window)
    window.update()
    if window._compose_card_mode:
        window._exit_email_card_mode()


# ── P0: message construction ─────────────────────────────────────────────

def test_build_email_message_is_multipart_alternative_with_both_parts(window):
    msg = window._build_email_message(
        "Subject", "to@test.dev",
        "<html><body><p style='color:red'>Rich <b>HTML</b></p></body></html>",
        "Rich HTML")
    assert msg.get_content_type() == "multipart/alternative"
    parts = msg.get_payload()
    types = [p.get_content_type() for p in parts]
    assert types == ["text/plain", "text/html"]
    html_part = parts[1].get_payload(decode=True).decode("utf-8")
    # Full HTML preserved — inline style intact, not flattened.
    assert "color:red" in html_part
    assert "<b>HTML</b>" in html_part


def test_compliance_footer_in_both_parts_of_the_real_message(window):
    msg = window._build_email_message(
        "S", "to@test.dev", "<html><body><p>hi</p></body></html>", "hi")
    plain = msg.get_payload()[0].get_payload(decode=True).decode("utf-8")
    html = msg.get_payload()[1].get_payload(decode=True).decode("utf-8")
    assert "STOP" in plain and "unsubscribe" in plain.lower()
    assert "STOP" in html and "unsubscribe" in html.lower()


def test_card_html_reaches_the_wire_unmodified_except_tokens_and_footer(window, monkeypatch):
    """End-to-end: a Visual HTML Card send must put the real card HTML —
    <style> block and inline styles intact — into the text/html part, with
    {name} substituted, NOT a plain-text flattening of it."""
    from src.ui import send_dialogs

    monkeypatch.setattr(send_dialogs, "show_send_confirmation",
                        lambda *a, **k: k.get("on_confirm", lambda: None)())
    window.contacts = [Contact(id=1, name="Priya", phone="+1000000001",
                               email="priya@test.dev")]
    window._enter_email_card_mode(CARD_HTML, "Deal for {name}")
    window.update()

    window._start_email_from_compose()
    assert _pump(window, lambda: bool(_FakeSMTP.sent)), \
        f"nothing was sent (status: {window.progress_status_var.get()!r})"
    _from, to_addr, raw = _FakeSMTP.sent[0]
    assert to_addr == "priya@test.dev"

    import email
    msg = email.message_from_string(raw)
    assert msg.get_content_type() == "multipart/alternative"
    html_part = None
    plain_part = None
    for p in msg.get_payload():
        if p.get_content_type() == "text/html":
            html_part = p.get_payload(decode=True).decode("utf-8")
        elif p.get_content_type() == "text/plain":
            plain_part = p.get_payload(decode=True).decode("utf-8")
    assert html_part is not None and plain_part is not None
    # The real card structure survives on the wire.
    assert "<style>" in html_part
    assert "border-radius:20px" in html_part
    assert 'href="https://example.com"' in html_part
    assert "Buy Now" in html_part
    # Personalised, not left as a raw token.
    assert "Hello Priya" in html_part
    assert "{name}" not in html_part
    # Footer added, nothing else stripped.
    assert "STOP" in html_part


def test_current_email_templates_returns_card_html_in_card_mode(window):
    window._enter_email_card_mode(CARD_HTML, "S")
    window.update()
    html_t, plain_t = window._current_email_templates()
    assert html_t == CARD_HTML
    assert "<" not in plain_t  # plain template is a text rendering
    assert "Buy Now" in plain_t


# ── P3: suppression ─────────────────────────────────────────────────────

def test_opted_out_and_bounced_contacts_are_excluded_from_the_send(window, monkeypatch):
    from src.ui import send_dialogs

    captured = {}
    monkeypatch.setattr(
        send_dialogs, "show_send_confirmation",
        lambda *a, **k: (captured.setdefault("count", a[2]),
                         captured.setdefault("note", k.get("exclusions_note", ""))))
    window.contacts = [
        Contact(id=1, name="Good", phone="+1", email="good@test.dev"),
        Contact(id=2, name="Gone", phone="+2", email="gone@test.dev", opted_out=True),
        Contact(id=3, name="Bounced", phone="+3", email="bad@test.dev", bounced=True),
        Contact(id=4, name="NoEmail", phone="+4", email=""),
    ]
    window._exit_email_card_mode()
    window._compose_em_body.delete("1.0", "end")
    window._compose_em_body.insert("1.0", "Hi {name}")
    window.update()
    window._start_email_from_compose()
    window.update()
    assert captured["count"] == 1
    assert "unsubscribed" in captured["note"]
    assert "bounced" in captured["note"]
    assert "no email" in captured["note"]


# ── P0: send test to myself ─────────────────────────────────────────────

def test_send_test_to_myself_sends_one_message_to_the_configured_account(window):
    window.contacts = [Contact(id=1, name="Priya", phone="+1", email="priya@test.dev")]
    window._enter_email_card_mode(CARD_HTML, "Deal for {name}")
    window.update()
    campaigns_before = len(window.db.get_campaigns())

    window._send_test_email_to_self()
    assert _pump(window, lambda: bool(_FakeSMTP.sent)), \
        f"test send produced nothing (status: {window.progress_status_var.get()!r})"
    assert len(_FakeSMTP.sent) == 1
    _from, to_addr, raw = _FakeSMTP.sent[0]
    assert to_addr == "me@test.dev"  # the configured SMTP account

    import email
    msg = email.message_from_string(raw)
    assert msg["Subject"].startswith("[TEST]")
    html = next(p.get_payload(decode=True).decode("utf-8")
                for p in msg.get_payload() if p.get_content_type() == "text/html")
    assert "Hello Priya" in html  # real substitution using the first contact
    assert "border-radius:20px" in html  # real card styling, not flattened
    # A test send must not create a campaign row.
    assert len(window.db.get_campaigns()) == campaigns_before


def test_send_test_to_myself_blocks_when_smtp_not_configured(window):
    original = window._em_user.get()
    window._em_user.set("")
    try:
        window._send_test_email_to_self()
        window.update()
        assert "SMTP not configured" in window.progress_status_var.get()
        assert not _FakeSMTP.sent
    finally:
        window._em_user.set(original)


# ── P2: recipient breakdown + last-run indicator ───────────────────────

def test_recipient_breakdown_counts_exclusions(window):
    window.contacts = [
        Contact(id=1, name="A", phone="+1", email="a@test.dev"),
        Contact(id=2, name="B", phone="+2", email="b@test.dev"),
        Contact(id=3, name="C", phone="+3", email="c@test.dev", opted_out=True),
        Contact(id=4, name="D", phone="+4", email="d@test.dev", bounced=True),
        Contact(id=5, name="E", phone="+5", email=""),
    ]
    b = window._email_recipient_breakdown()
    assert len(b["eligible"]) == 2
    assert b["unsubscribed"] == 1
    assert b["bounced"] == 1
    assert b["no_email"] == 1

    window._refresh_compose_email_recipients()
    window.update()
    assert window._em_compose_count_var.get().startswith("2 ")
    detail = window._em_recip_detail_var.get()
    assert "1 unsubscribed" in detail
    assert "1 previously bounced" in detail


def test_last_run_indicator_is_set_after_a_send(window, monkeypatch):
    from src.ui import send_dialogs
    monkeypatch.setattr(send_dialogs, "show_send_confirmation",
                        lambda *a, **k: k.get("on_confirm", lambda: None)())
    # Suppress the follow-up report dialog and bounce-check timer.
    window.contacts = [Contact(id=1, name="A", phone="+1", email="a@test.dev")]
    window._exit_email_card_mode()
    window._compose_em_body.delete("1.0", "end")
    window._compose_em_body.insert("1.0", "Hi {name}")
    window._em_last_run_var.set("")
    window.update()

    window._start_email_from_compose()
    assert _pump(window, lambda: bool(window._em_last_run_var.get()), timeout_s=8.0)
    assert "1 sent" in window._em_last_run_var.get()
    assert "not confirmed delivered" in window._em_last_run_var.get()
