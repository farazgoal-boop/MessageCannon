"""Regression coverage for Item 5 of the Live Testing Findings pass: Compose's
WhatsApp tab appeared to show only 1 of 9 real contacts.

Investigated by direct empirical inspection (not just code reading) against
the real 9-contact production database: `_render_compose_contacts` renders
every contact in `self.contacts` unconditionally (confirmed: all 9 render as
real `CTkCheckBox` rows, unfiltered by phone/email). The actual "1" the user
saw was `compose_contacts_var` — a *selection* counter (`_get_selected_
contacts()`, driven by which checkboxes are ticked, starting at 0 by
default), previously displayed as just "N selected" with no denominator, so
"1 selected" is trivially misreadable as "only 1 of my contacts is usable."
This was correct filtering behavior, not a bug — per this item's own
explicit fallback ("if it's correct filtering, make the UI say so
explicitly"), the fix makes the denominator visible: "N of M selected".
"""

from __future__ import annotations

import customtkinter as ctk

from src.models import Contact


def test_all_contacts_render_in_the_whatsapp_checklist_unfiltered(app):
    original_contacts = app.contacts
    original_vars = dict(app.contact_selection_vars)
    try:
        app.contacts = [
            Contact(id=9001, phone="+15550000001", email="", name="Phone Only"),
            Contact(id=9002, phone="", email="email1@test.dev", name="Email Only"),
            Contact(id=9003, phone="+15550000003", email="both@test.dev", name="Both"),
        ]
        app._sync_contact_selection()
        app._render_compose_contacts()
        app.update()

        checkboxes = [w for w in app.compose_contacts_frame.winfo_children()
                      if isinstance(w, ctk.CTkCheckBox)]
        assert len(checkboxes) == 3
        names = {cb.cget("text").split("  |")[0] for cb in checkboxes}
        assert names == {"Phone Only", "Email Only", "Both"}
    finally:
        app.contacts = original_contacts
        app.contact_selection_vars = original_vars
        app._render_compose_contacts()
        app.update()


def test_selected_summary_shows_denominator_not_just_a_bare_count(app):
    original_contacts = app.contacts
    original_vars = dict(app.contact_selection_vars)
    try:
        app.contacts = [
            Contact(id=9101, phone="+15550000001", email="", name="A"),
            Contact(id=9102, phone="+15550000002", email="", name="B"),
            Contact(id=9103, phone="+15550000003", email="", name="C"),
        ]
        app._sync_contact_selection()
        app._render_compose_contacts()
        app._update_compose_summary()
        app.update()

        assert app.compose_contacts_var.get() == "0 of 3 selected"

        key = app._contact_key(app.contacts[0], 0)
        app.contact_selection_vars[key].set(True)
        app._update_compose_summary()

        assert app.compose_contacts_var.get() == "1 of 3 selected"
    finally:
        app.contacts = original_contacts
        app.contact_selection_vars = original_vars
        app._render_compose_contacts()
        app._update_compose_summary()
        app.update()


def test_opted_out_contacts_excluded_from_available_denominator(app):
    original_contacts = app.contacts
    original_vars = dict(app.contact_selection_vars)
    try:
        app.contacts = [
            Contact(id=9201, phone="+15550000001", email="", name="Active"),
            Contact(id=9202, phone="+15550000002", email="", name="OptedOut", opted_out=True),
        ]
        app._sync_contact_selection()
        app._render_compose_contacts()
        app._update_compose_summary()
        app.update()

        # 2 rows render (opted-out shown but disabled), only 1 counts as available
        checkboxes = [w for w in app.compose_contacts_frame.winfo_children()
                      if isinstance(w, ctk.CTkCheckBox)]
        assert len(checkboxes) == 2
        assert app.compose_contacts_var.get() == "0 of 1 selected"
    finally:
        app.contacts = original_contacts
        app.contact_selection_vars = original_vars
        app._render_compose_contacts()
        app._update_compose_summary()
        app.update()
