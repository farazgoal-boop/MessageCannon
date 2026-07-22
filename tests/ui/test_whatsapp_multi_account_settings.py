"""Settings UI coverage for multi-number WhatsApp account management
(Item 7, final completion pass) -- _render_whatsapp_accounts /
_add_whatsapp_account / _remove_whatsapp_account on MainWindow. Uses a
dedicated, module-scoped, fresh-DB MainWindow (same pattern as
test_contact_delete.py) so account CRUD never reaches the live production
database.
"""

import tkinter as tk

import pytest

from src.core import whatsapp_accounts as wa_accounts


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
    fresh_db_path = str(tmp_path_factory.mktemp("wa_multi_account") / "test.db")
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


@pytest.fixture(autouse=True)
def _reset_accounts(window):
    wa_accounts.save_accounts(window.db, [])
    window._render_whatsapp_accounts()
    yield
    wa_accounts.save_accounts(window.db, [])
    window._render_whatsapp_accounts()


def _labels_in_list(window):
    texts = []
    for child in window.wa_accounts_list_frame.winfo_children():
        for grandchild in child.winfo_children():
            try:
                text = grandchild.cget("text")
            except Exception:
                continue
            if text:
                texts.append(str(text))
    return texts


def test_empty_state_shown_with_no_accounts(window):
    texts = " ".join(_labels_in_list(window))
    assert "No additional numbers configured yet" in texts


def test_add_account_via_ui_renders_new_row(window):
    window._wa_new_account_var.set("Sales Line")
    window._add_whatsapp_account()
    window.update()

    texts = " ".join(_labels_in_list(window))
    assert "Sales Line" in texts
    assert window._wa_new_account_var.get() == ""  # cleared after a successful add

    accounts = wa_accounts.list_accounts(window.db)
    assert any(a.label == "Sales Line" for a in accounts)


def test_add_duplicate_account_shows_error_and_does_not_duplicate(window):
    window._wa_new_account_var.set("Support Line")
    window._add_whatsapp_account()
    window.update()

    window._wa_new_account_var.set("Support Line")
    window._add_whatsapp_account()
    window.update()

    accounts = wa_accounts.list_accounts(window.db)
    matching = [a for a in accounts if a.label == "Support Line"]
    assert len(matching) == 1


def test_remove_account_via_ui_removes_row(window):
    window._wa_new_account_var.set("Temp Line")
    window._add_whatsapp_account()
    window.update()
    account = next(a for a in wa_accounts.list_accounts(window.db) if a.label == "Temp Line")

    window._remove_whatsapp_account(account)
    window.update()

    texts = " ".join(_labels_in_list(window))
    assert "Temp Line" not in texts
    accounts = wa_accounts.list_accounts(window.db)
    assert not any(a.label == "Temp Line" for a in accounts)
