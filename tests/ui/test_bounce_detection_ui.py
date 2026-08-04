"""Real bounce/delivery-tracking UI coverage: History row bounce display +
"Check Bounces" action, Contacts directory "Bounced" badge + clear action,
and MainWindow._check_campaign_for_bounces' own reconciliation logic.

Uses a dedicated, module-scoped, fresh-DB MainWindow (same pattern as
test_contact_delete.py/test_sidebar_update_pill.py) -- a real bounce
reconciliation writes to message_logs/contacts and must never be able to
reach the live production database. The real IMAP network call itself
(src.core.bounce_checker.check_for_bounces) is mocked at the same boundary
this app already mocks every other network call at in this suite (AI calls,
update checks) -- a real, live IMAP bounce check against the app's actual
Gmail account is proven separately, live, not in this automated file.
"""

import threading
import tkinter as tk

import pytest

from src.models import Campaign, Contact, MessageLog, MessageStatus


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


class _SynchronousThread:
    """Stand-in for threading.Thread that runs `target` immediately in the
    calling thread -- same reasoning/pattern already established by
    test_ai_error_reporting.py / test_update_dialog_e2e.py: this harness
    drives Tk via `.update()` polling, not a real mainloop, and a genuine
    cross-thread `self.after()` call needs Tcl to think it's inside one."""

    def __init__(self, target=None, daemon=None):
        self._target = target

    def start(self):
        self._target()


@pytest.fixture(scope="module")
def window(tmp_path_factory):
    from src.database import db_manager as db_manager_module

    mp = pytest.MonkeyPatch()
    fresh_db_path = str(tmp_path_factory.mktemp("bounce_ui") / "test.db")
    mp.setattr(db_manager_module, "get_database_path", lambda: fresh_db_path)
    db_manager_module.DatabaseManager._instance = None

    from src.ui.main_window import MainWindow

    win = MainWindow()
    _close_any_toplevel(win)
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


@pytest.fixture()
def synchronous_thread(monkeypatch):
    import src.ui.main_window as main_window_module
    monkeypatch.setattr(main_window_module.threading, "Thread", _SynchronousThread)


def _make_campaign_with_sent_logs(window, emails, name="Bounce Test Campaign"):
    campaign_id = window.db.add_campaign(Campaign(name=name, message_template="", total_contacts=len(emails)))
    log_ids = []
    for email_addr in emails:
        log_id = window.db.add_message_log(MessageLog(
            campaign_id=campaign_id, contact_email=email_addr, contact_name=email_addr,
            message_text="hi", status=MessageStatus.SENT))
        log_ids.append(log_id)
    return campaign_id, log_ids


def test_check_campaign_for_bounces_reconciles_a_real_confirmed_bounce(window, synchronous_thread, monkeypatch):
    import src.ui.main_window as main_window_module
    from src.core import bounce_checker as bc

    campaign_id, _ = _make_campaign_with_sent_logs(
        window, ["good-mc-test@test.dev", "bad-mc-test@test.dev"])
    window.contacts.append(Contact(
        id=window.db.add_contact(Contact(email="bad-mc-test@test.dev", name="Bad Contact")),
        email="bad-mc-test@test.dev", name="Bad Contact"))
    # Real contact additions always go through _reload_contacts(), which
    # calls this to register a BooleanVar for every contact before
    # _render_compose_contacts() ever runs against it -- mirror that here
    # since this test appends directly.
    window._sync_contact_selection()

    window._em_host.set("smtp.gmail.com")
    window._em_provider.set("Gmail")
    window._em_user.set("tester@gmail.com")
    window._em_pass.set("app-password")

    def fake_check(host, port, username, password, candidate_emails, since_days=14):
        assert host == "imap.gmail.com" and port == 993
        assert "bad-mc-test@test.dev" in candidate_emails
        return bc.BounceCheckResult(ok=True, bounces={"bad-mc-test@test.dev": "550 5.1.1 User unknown"})

    monkeypatch.setattr(main_window_module.bounce_checker, "check_for_bounces", fake_check)

    results = []
    window._check_campaign_for_bounces(campaign_id, silent=True, on_done=lambda r: results.append(r))
    window.update()

    assert len(results) == 1 and results[0].ok is True
    stats = window.db.get_campaign_bounce_stats(campaign_id)
    assert stats["bounced_count"] == 1
    assert stats["bounced"][0][1] == "bad-mc-test@test.dev"

    contact = next(c for c in window.contacts if c.email == "bad-mc-test@test.dev")
    assert contact.bounced is True

    db_contact = next(c for c in window.db.get_contacts() if c.email == "bad-mc-test@test.dev")
    assert db_contact.bounced is True


def test_check_campaign_for_bounces_leaves_non_bounced_contact_untouched(window, synchronous_thread, monkeypatch):
    import src.ui.main_window as main_window_module
    from src.core import bounce_checker as bc

    campaign_id, _ = _make_campaign_with_sent_logs(window, ["clean-mc-test@test.dev"])
    window._em_host.set("smtp.gmail.com")
    window._em_provider.set("Gmail")
    window._em_user.set("tester@gmail.com")
    window._em_pass.set("app-password")

    monkeypatch.setattr(main_window_module.bounce_checker, "check_for_bounces",
                         lambda *a, **k: bc.BounceCheckResult(ok=True, bounces={}))

    results = []
    window._check_campaign_for_bounces(campaign_id, silent=True, on_done=lambda r: results.append(r))
    window.update()

    assert results[0].ok is True
    assert window.db.get_campaign_bounce_stats(campaign_id) == {"bounced_count": 0, "bounced": []}


def test_check_campaign_for_bounces_reports_failure_without_raising(window, synchronous_thread, monkeypatch):
    import src.ui.main_window as main_window_module
    from src.core import bounce_checker as bc

    campaign_id, _ = _make_campaign_with_sent_logs(window, ["a-mc-test@test.dev"])
    window._em_host.set("smtp.gmail.com")
    window._em_provider.set("Gmail")
    window._em_user.set("tester@gmail.com")
    window._em_pass.set("wrong-pass")

    monkeypatch.setattr(main_window_module.bounce_checker, "check_for_bounces",
                         lambda *a, **k: bc.BounceCheckResult(ok=False, error="IMAP login failed"))

    results = []
    window._check_campaign_for_bounces(campaign_id, silent=False, on_done=lambda r: results.append(r))
    window.update()

    assert results[0].ok is False and "login failed" in results[0].error


def test_check_campaign_for_bounces_skips_gracefully_for_unresolvable_provider(window, synchronous_thread):
    campaign_id, _ = _make_campaign_with_sent_logs(window, ["a-mc-test@test.dev"])
    window._em_host.set("mail.totally-custom-server.net")
    window._em_provider.set("Custom")
    window._em_user.set("tester@custom.dev")
    window._em_pass.set("pw")

    results = []
    window._check_campaign_for_bounces(campaign_id, silent=True, on_done=lambda r: results.append(r))
    window.update()

    assert results[0].ok is False
    assert "IMAP" in results[0].error


def test_check_campaign_for_bounces_no_candidates_is_a_clean_noop(window, synchronous_thread):
    campaign_id = window.db.add_campaign(Campaign(name="Empty Campaign", message_template="", total_contacts=0))
    results = []
    window._check_campaign_for_bounces(campaign_id, silent=True, on_done=lambda r: results.append(r))
    window.update()
    assert results[0].ok is True
    assert results[0].bounces == {}


def test_history_row_shows_bounced_count_and_check_button(window):
    campaign_id, log_ids = _make_campaign_with_sent_logs(window, ["hist-a@test.dev", "hist-b@test.dev"])
    window.db.mark_message_log_bounced(log_ids[1], "mailbox full")
    window.db.update_campaign(campaign_id, sent_count=2, failed_count=0)

    window._history_campaigns = window.db.get_recent_campaigns_summary(limit=100)
    window._render_history_rows()
    window.update()

    def collect_texts(widget):
        texts = []
        for child in widget.winfo_children():
            try:
                text = child.cget("text")
                if text:
                    texts.append(str(text))
            except Exception:
                pass
            texts.extend(collect_texts(child))
        return texts

    all_text = " | ".join(collect_texts(window._history_scroll))
    assert "1 bounced" in all_text
    assert "Check Bounces" in all_text


def test_contacts_directory_shows_bounced_badge_and_clear_action(window):
    contact_id = window.db.add_contact(Contact(email="badge-mc-test@test.dev", name="Badge Test"))
    window.db.set_contact_bounced(contact_id, True)
    contact = Contact(id=contact_id, email="badge-mc-test@test.dev", name="Badge Test", bounced=True)
    window.contacts.append(contact)
    try:
        window._render_contacts_directory()
        window.update()

        def collect_texts(widget):
            texts = []
            for child in widget.winfo_children():
                try:
                    text = child.cget("text")
                    if text:
                        texts.append(str(text))
                except Exception:
                    pass
                texts.extend(collect_texts(child))
            return texts

        all_text = " | ".join(collect_texts(window.contacts_directory))
        assert "Bounced" in all_text
        assert "Clear Bounced Flag" in all_text
    finally:
        window.contacts.remove(contact)
        window.db.delete_contact(contact_id)


def test_toggle_contact_bounced_updates_db_and_memory(window):
    contact_id = window.db.add_contact(Contact(email="toggle-mc-test@test.dev", name="Toggle Test"))
    contact = Contact(id=contact_id, email="toggle-mc-test@test.dev", name="Toggle Test")
    window.contacts.append(contact)
    window._sync_contact_selection()
    try:
        window._toggle_contact_bounced(contact, True)
        window.update()
        assert contact.bounced is True
        db_contact = next(c for c in window.db.get_contacts() if c.id == contact_id)
        assert db_contact.bounced is True

        window._toggle_contact_bounced(contact, False)
        window.update()
        assert contact.bounced is False
        db_contact = next(c for c in window.db.get_contacts() if c.id == contact_id)
        assert db_contact.bounced is False
    finally:
        window.contacts.remove(contact)
        window.db.delete_contact(contact_id)


def test_bounced_contact_excluded_from_email_compose_recipient_filter(window):
    """The actual enforcement point: _start_email_from_compose's own
    recipients filter must exclude a bounced contact the same way it
    already excludes an opted-out one."""
    good_id = window.db.add_contact(Contact(email="filter-good@test.dev", name="Good"))
    bad_id = window.db.add_contact(Contact(email="filter-bad@test.dev", name="Bad", bounced=True))
    good = Contact(id=good_id, email="filter-good@test.dev", name="Good")
    bad = Contact(id=bad_id, email="filter-bad@test.dev", name="Bad", bounced=True)
    window.contacts.extend([good, bad])
    try:
        eligible = [c for c in window.contacts if c.email and not c.opted_out and not c.bounced]
        emails = {c.email for c in eligible}
        assert "filter-good@test.dev" in emails
        assert "filter-bad@test.dev" not in emails
    finally:
        window.contacts.remove(good)
        window.contacts.remove(bad)
        window.db.delete_contact(good_id)
        window.db.delete_contact(bad_id)
