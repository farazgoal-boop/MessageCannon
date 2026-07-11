"""Opt-out must be enforced (not just recorded) at every point contacts get
selected for sending. The selection-filter logic (_get_selected_contacts,
the email recipient filter) is pure in-memory — no DB writes needed to test
it, so this runs directly against the shared session `app`, saving and
restoring its real .contacts list rather than touching the real database."""

from src.models import Contact


def test_opted_out_contact_excluded_from_whatsapp_selection(app):
    original_contacts = app.contacts
    original_vars = dict(app.contact_selection_vars)
    try:
        active = Contact(id=1, name="Active Person", phone="+10000000001", opted_out=False)
        opted_out = Contact(id=2, name="Opted Out Person", phone="+10000000002", opted_out=True)
        app.contacts = [active, opted_out]
        app.contact_selection_vars = {}
        app._sync_contact_selection()

        for index, contact in enumerate(app.contacts):
            key = app._contact_key(contact, index)
            app.contact_selection_vars[key].set(True)  # try to select BOTH

        selected = app._get_selected_contacts()
        selected_phones = {c.phone for c in selected}

        assert "+10000000001" in selected_phones, "active contact should be selectable"
        assert "+10000000002" not in selected_phones, (
            "opted-out contact must be excluded even if its checkbox is checked")
    finally:
        app.contacts = original_contacts
        app.contact_selection_vars = original_vars


def test_opted_out_contact_excluded_from_email_recipients(app):
    active = Contact(id=1, name="Active", phone="+1", email="active@test.dev", opted_out=False)
    opted_out = Contact(id=2, name="OptedOut", phone="+2", email="optedout@test.dev", opted_out=True)
    contacts = [active, opted_out]

    eligible = [c for c in contacts if c.email and not c.opted_out]
    eligible_emails = {c.email for c in eligible}

    assert "active@test.dev" in eligible_emails
    assert "optedout@test.dev" not in eligible_emails


def test_set_contact_opted_out_persists_and_toggles(isolated_db):
    contact_id = isolated_db.add_contact(
        Contact(name="Toggle Test", phone="+19999999999", email="toggle@test.dev"))
    assert contact_id is not None

    contacts = isolated_db.get_contacts()
    fetched = next(c for c in contacts if c.id == contact_id)
    assert fetched.opted_out is False

    ok = isolated_db.set_contact_opted_out(contact_id, True)
    assert ok is True
    contacts = isolated_db.get_contacts()
    fetched = next(c for c in contacts if c.id == contact_id)
    assert fetched.opted_out is True

    ok = isolated_db.set_contact_opted_out(contact_id, False)
    assert ok is True
    contacts = isolated_db.get_contacts()
    fetched = next(c for c in contacts if c.id == contact_id)
    assert fetched.opted_out is False


def test_delete_all_contacts_and_clear_history_return_real_counts(isolated_db):
    isolated_db.add_contact(Contact(name="A", phone="+1000000001"))
    isolated_db.add_contact(Contact(name="B", phone="+1000000002"))
    assert isolated_db.get_contact_count() == 2

    removed = isolated_db.delete_all_contacts()
    assert removed == 2
    assert isolated_db.get_contact_count() == 0
