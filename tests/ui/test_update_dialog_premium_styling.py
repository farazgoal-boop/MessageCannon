"""Item 29 of the Final Premium Polish Pass, plus a follow-up real visual
pass (2026-07-28, live user feedback): the sidebar update badge (Item
8/Round-2-Item-2) and its `UpdateDialog` (also Item 8), checked against the
design system Items 26-28 already established, without breaking the
already-proven click -> dialog -> download -> install flow
(`test_update_dialog_e2e.py`, `test_sidebar_update_pill.py`, both re-run
unchanged after this item's changes).

Item 29's original pass fixed the badge hover color and added *a* card
around the version info, but the user reported it still read as a generic
system dialog after actually seeing it live: too much empty grey space in
the release-notes box (it stretched to fill all leftover height via
grid_rowconfigure(weight=1), which looks like a near-empty rectangle for
typically-short real release notes), and the three footer buttons (Later /
View on GitHub / Download & Install) all looked the same flat weight
instead of a real primary/secondary/tertiary hierarchy.

Follow-up fix, this file's current version:
1. The title is now a standalone header row directly on the dialog's own
   background — matching the REAL established precedent
   (`SendConfirmationDialog`'s title also sits outside its stats card, not
   inside it; Item 29's original version had wrongly put the title inside
   the card).
2. The version-info card is now a real two-cell "Installed" / "Available"
   stats block, the same visual language as `SendConfirmationDialog`'s
   recipients/delay/ETA cells, instead of two differently-weighted bare
   labels.
3. The release-notes box is now a fixed, content-sized height (120px) with
   its own real border, not a stretch-to-fill textbox — no more large empty
   grey area.
4. Footer buttons now have three real tiers: "Later" is a ghost/ext-link
   style (transparent until hovered, muted text) since it's the least
   important action; "View on GitHub" is the outline-secondary style
   already established by History's "Duplicate" button and Compose's
   Pause/Resume (`fg_color=BG_INNER` + a real border + `ACCENT_TEXT`,
   confirmed WCAG-passing unlike plain `T.ACCENT` as text_color) since it's
   a real but explicitly secondary/fallback action; "Download & Install"
   stays the one filled `T.ACCENT` primary action, unchanged.
"""

from __future__ import annotations

import customtkinter as ctk

import src.ui.theme as T


def test_sidebar_update_badge_hover_matches_the_established_badge_bg_pattern(app):
    badge = app.sidebar_update_badge
    assert badge.cget("fg_color") == T.BADGE_BG
    assert badge.cget("hover_color") == T.BG_BORDER
    assert badge.cget("fg_color") != badge.cget("hover_color")


def test_update_dialog_title_is_a_standalone_header_matching_send_confirmation_precedent(app):
    """The title sits directly on the dialog's own background, size=18 --
    matching SendConfirmationDialog's real precedent (its title is also
    outside the stats card), not wrapped inside the version-info card."""
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
        for child in dialog.winfo_children():
            if isinstance(child, ctk.CTkLabel):
                try:
                    if "v9.9.9 is available" in child.cget("text"):
                        title_label = child
                except Exception:
                    pass
        assert title_label is not None, "expected to find the version title label as a direct dialog child"
        assert title_label.cget("font").cget("size") == 18
    finally:
        dialog.destroy()


def test_update_dialog_version_info_is_a_real_two_cell_stats_card(app):
    """Same visual language as SendConfirmationDialog's recipients/delay/ETA
    cells -- a real bordered T.BG_SURFACE card with "Installed"/"Available"
    cells, not two bare, differently-weighted labels."""
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
        texts = []
        version_card = None

        def walk(widget):
            nonlocal version_card
            for child in widget.winfo_children():
                if isinstance(child, ctk.CTkFrame) and child.cget("fg_color") == T.BG_SURFACE:
                    version_card = child
                if isinstance(child, ctk.CTkLabel):
                    try:
                        texts.append(child.cget("text"))
                    except Exception:
                        pass
                walk(child)

        walk(dialog)
        assert version_card is not None, "expected a real bordered BG_SURFACE stats card"
        assert version_card.cget("border_width") >= 1
        assert "Installed" in texts
        assert "Available" in texts
        assert "v1.0.0" in texts
        assert "v9.9.9" in texts
    finally:
        dialog.destroy()


def test_update_dialog_notes_box_is_fixed_height_not_stretch_filled(app):
    """The real fix for "too much empty grey space": a fixed content-sized
    height instead of grid_rowconfigure(weight=1) stretching a mostly-empty
    textbox to fill the whole dialog."""
    from src.ui.update_dialog import UpdateDialog
    from src.core.update_checker import UpdateInfo

    info = UpdateInfo(
        version="9.9.9", tag="v9.9.9", release_notes="short notes",
        release_url="https://example.invalid/releases/v9.9.9",
        asset_url=None, asset_name=None,
    )
    dialog = UpdateDialog(app, info, "1.0.0")
    app.update()
    try:
        assert dialog.grid_rowconfigure(3)["weight"] == 0
    finally:
        dialog.destroy()


def test_update_dialog_footer_buttons_have_three_real_tiers(app):
    """Later (ghost) / View on GitHub (outline-secondary, History's
    Duplicate-button pattern) / Download & Install (filled primary) --
    three visually distinct tiers, not three same-weight buttons."""
    from src.ui.update_dialog import UpdateDialog
    from src.core.update_checker import UpdateInfo

    info = UpdateInfo(
        version="9.9.9", tag="v9.9.9", release_notes="notes",
        release_url="https://example.invalid/releases/v9.9.9",
        asset_url="https://example.invalid/asset.exe", asset_name="asset.exe",
    )
    dialog = UpdateDialog(app, info, "1.0.0")
    app.update()
    try:
        later_btn = None
        github_btn = None

        def walk(widget):
            nonlocal later_btn, github_btn
            for child in widget.winfo_children():
                if isinstance(child, ctk.CTkButton):
                    text = child.cget("text")
                    if text == "Later":
                        later_btn = child
                    elif text == "View on GitHub":
                        github_btn = child
                walk(child)

        walk(dialog)
        assert later_btn is not None and github_btn is not None

        # Later: ghost/ext-link -- transparent until hovered, muted text.
        assert later_btn.cget("fg_color") == "transparent"
        assert later_btn.cget("text_color") == T.TEXT_MUTED

        # View on GitHub: outline-secondary, History Duplicate-button style
        # -- a real border and ACCENT_TEXT, not a flat BADGE_BG fill.
        assert github_btn.cget("fg_color") == T.BG_INNER
        assert github_btn.cget("border_width") >= 1
        assert github_btn.cget("text_color") == T.ACCENT_TEXT

        # The three tiers must be visibly distinct from each other, not the
        # same color repeated under different names.
        assert later_btn.cget("fg_color") != github_btn.cget("fg_color")
        assert github_btn.cget("fg_color") != dialog._install_btn.cget("fg_color")
    finally:
        dialog.destroy()
