"""Item 29 of the Final Premium Polish Pass: a final premium-consistency pass
on the sidebar update badge (Item 8/Round-2-Item-2) and its `UpdateDialog`
(also Item 8), checked against the design system Items 26-28 already
established, without breaking the already-proven click -> dialog -> download
-> install flow (`test_update_dialog_e2e.py`, `test_sidebar_update_pill.py`,
both re-run unchanged after this item's changes).

Two real, confirmed inconsistencies found and fixed:

1. **Sidebar update badge's hover color**: `hover_color=T.BG_SURFACE` was the
   sole `T.BADGE_BG`-filled interactive element app-wide not using
   `T.BG_BORDER` as its hover companion — already standardized on every
   other `BADGE_BG` button/dropdown in Items 26-27 (Contacts "Refresh",
   "Import Contacts", the Compose/Settings dropdowns, etc). Normalized to
   match.
2. **`UpdateDialog` had no card framing at all** — two bare labels (title +
   "You have vX installed") sat directly on the dialog's `T.BG_MAIN` root
   background, unlike its sibling dialogs: `SendConfirmationDialog`'s own
   recipients/delay/ETA "stats" strip is the direct precedent for wrapping
   key info in a real bordered `T.BG_SURFACE` card. Wrapped the same way
   here. The title font (was size=16) also didn't match the established
   size=18 dialog-title convention used by `SendConfirmationDialog`/
   `AIComposeDialog`/`ContactImportReviewDialog` — bumped to match. Dialog
   height bumped 420->450 so the new card's padding doesn't squeeze the
   release-notes box under the same fixed size.
"""

from __future__ import annotations

import customtkinter as ctk

import src.ui.theme as T


def test_sidebar_update_badge_hover_matches_the_established_badge_bg_pattern(app):
    badge = app.sidebar_update_badge
    assert badge.cget("fg_color") == T.BADGE_BG
    assert badge.cget("hover_color") == T.BG_BORDER
    assert badge.cget("fg_color") != badge.cget("hover_color")


def test_update_dialog_wraps_version_info_in_a_real_card(app):
    from src.ui.update_dialog import UpdateDialog
    from src.core.update_checker import UpdateInfo

    info = UpdateInfo(
        version="9.9.9", tag="v9.9.9", release_notes="notes",
        release_url="https://example.invalid/releases/v9.9.9",
        asset_url=None, asset_name=None,
    )
    dialog = UpdateDialog(app, info, "1.0.0")
    app.update()
    try:
        title_label = None
        version_card = None

        def walk(widget):
            nonlocal title_label, version_card
            for child in widget.winfo_children():
                if isinstance(child, ctk.CTkLabel):
                    try:
                        if child.cget("text") == "MessageCannon Pro v9.9.9 is available":
                            title_label = child
                            version_card = widget
                    except Exception:
                        pass
                walk(child)

        walk(dialog)
        assert title_label is not None, "expected to find the version title label"
        assert version_card is not None
        # The real fix: a genuine bordered card, not a bare label directly
        # on the dialog's own T.BG_MAIN root.
        assert isinstance(version_card, ctk.CTkFrame)
        assert version_card.cget("fg_color") == T.BG_SURFACE
        assert version_card.cget("border_width") >= 1
        assert title_label.cget("font").cget("size") == 18
    finally:
        dialog.destroy()
