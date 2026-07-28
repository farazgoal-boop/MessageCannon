"""Real bug found while investigating a live report that Card Creator's
"Crop" button stayed disabled after what looked like a successful
drag-drop logo upload: `card_creator_tab.py`'s `_on_icon_drop` (and,
confirmed via grep, `contact_import_review.py`'s own `_on_drop` -- the same
logic, duplicated byte-for-byte) never handled a real, documented
tkinterdnd2 cross-platform quirk: some drag sources hand back a `file://`
URI instead of a plain filesystem path. A `file://` URI fails
`Path(...).is_file()`, so a perfectly real dropped file could silently fail
to import/upload.

The parsing itself was extracted to `utils/helpers.parse_dropped_file_path`
(tested directly, exhaustively, in `test_card_creator_premium.py`) so both
call sites can't drift apart again. This file closes the loop for the
Contact Import Review dialog's own drop zone -- confirming the same real
fix applies there too, not just in Card Creator.
"""

from __future__ import annotations

import urllib.parse

from src.ui.contact_import_review import ContactImportReviewDialog


class _FakeDropEvent:
    def __init__(self, data: str):
        self.data = data


def test_contact_import_on_drop_handles_a_file_uri(app, tmp_path, monkeypatch):
    """The literal sibling repro: a real file, dropped via a file:// URI
    (not a plain path), must still reach _start_analysis with the correct,
    real filesystem path -- not the raw, unusable URI string."""
    dialog = ContactImportReviewDialog(app)
    try:
        real_path = tmp_path / "contacts.csv"
        real_path.write_text("name,phone\nA,+10000000001\n")

        calls = []
        monkeypatch.setattr(dialog, "_start_analysis", lambda p: calls.append(p))

        uri = "file:///" + urllib.parse.quote(str(real_path).replace("\\", "/"), safe="/:")
        event = _FakeDropEvent(f"{{{uri}}}")
        dialog._on_drop(event)

        assert calls == [str(real_path).replace("\\", "/")]
    finally:
        dialog.destroy()
        app.update()


def test_contact_import_on_drop_still_handles_a_plain_braced_path(app, monkeypatch):
    """Regression guard: the pre-existing, already-working common case (a
    single Tcl-braced path with a space) must be completely unaffected by
    routing through the shared, extracted parser."""
    dialog = ContactImportReviewDialog(app)
    try:
        calls = []
        monkeypatch.setattr(dialog, "_start_analysis", lambda p: calls.append(p))

        event = _FakeDropEvent("{C:/Users/HAROON TRADERS/Desktop/contacts.csv}")
        dialog._on_drop(event)

        assert calls == ["C:/Users/HAROON TRADERS/Desktop/contacts.csv"]
    finally:
        dialog.destroy()
        app.update()
