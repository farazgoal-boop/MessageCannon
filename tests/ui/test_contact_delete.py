"""Per-row contact delete (Item 2 of the final completion pass) --
_delete_contact_row on MainWindow, wired to a "Delete" button in each
Contacts-directory row. Uses a dedicated, module-scoped, fresh-DB MainWindow
(same reasoning as test_sidebar_update_pill.py/test_status_bar.py): a real
delete must never be able to reach the live production database, and
messagebox.askyesno is monkeypatched so the confirm step never blocks on a
real OS dialog during the test run.
"""

import tkinter as tk
from tkinter import messagebox

import pytest

from src.models import Contact


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
    fresh_db_path = str(tmp_path_factory.mktemp("contact_delete") / "test.db")
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


def _add_test_contact(window, name: str, phone: str) -> Contact:
    contact_id = window.db.add_contact(Contact(name=name, phone=phone))
    contact = Contact(id=contact_id, name=name, phone=phone)
    window.contacts.append(contact)
    return contact


def test_delete_contact_row_removes_from_db_and_memory(window, monkeypatch):
    contact = _add_test_contact(window, "Delete Me", "+19999990001")
    monkeypatch.setattr(messagebox, "askyesno", lambda *a, **k: True)

    window._delete_contact_row(contact)
    window.update()

    assert contact.id not in {c.id for c in window.contacts}
    remaining = window.db.get_contacts()
    assert contact.id not in {c.id for c in remaining}


def test_delete_contact_row_cancelled_leaves_contact_intact(window, monkeypatch):
    contact = _add_test_contact(window, "Keep Me", "+19999990002")
    monkeypatch.setattr(messagebox, "askyesno", lambda *a, **k: False)

    window._delete_contact_row(contact)
    window.update()

    assert contact.id in {c.id for c in window.contacts}
    remaining = window.db.get_contacts()
    assert contact.id in {c.id for c in remaining}

    # Clean up for test isolation (doesn't affect other tests, but keeps the
    # fixture's DB tidy for anyone reading it while debugging).
    monkeypatch.setattr(messagebox, "askyesno", lambda *a, **k: True)
    window._delete_contact_row(contact)
    window.update()


def test_delete_button_present_in_rendered_contact_row(window, monkeypatch):
    contact = _add_test_contact(window, "Row Render Test", "+19999990003")
    monkeypatch.setattr(messagebox, "askyesno", lambda *a, **k: True)
    try:
        window._render_contacts_directory()
        window.update()

        def find_delete_buttons(widget):
            found = []
            for child in widget.winfo_children():
                text = None
                try:
                    text = child.cget("text")
                except Exception:
                    pass
                if text and "Delete" in str(text):
                    found.append(child)
                found.extend(find_delete_buttons(child))
            return found

        buttons = find_delete_buttons(window.contacts_directory)
        assert len(buttons) >= 1, "expected at least one 'Delete' button rendered in the directory"
    finally:
        window._delete_contact_row(contact)
        window.update()
