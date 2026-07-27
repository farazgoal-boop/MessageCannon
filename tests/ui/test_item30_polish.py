"""Item 30 of the Final Premium Polish Pass: an independent screen-by-screen
UX review, beyond Items 25-29's own explicit checklist.

Two real, confirmed findings, verified below:

1. **A genuine performance bug, not just a style nit**: `_show_view` calls
   `_on_header_search()` on *every* navigation to Contacts (or History),
   unconditionally -- but every real data mutation (import, per-row delete,
   opt-out toggle) already calls `_render_contacts_directory()` directly
   right after it changes anything. So re-rendering the *entire* directory
   (destroy + rebuild every card/button) again on a plain, unchanged
   navigation is pure redundant work. Measured directly via an isolated
   script before touching anything: ~1.0-1.9s per navigation for this app's
   real 9-contact directory, confirmed reproducible across 5 repeated calls
   (not machine noise) -- and confirmed via `tests/ui/test_navigation_timing.py`
   failing specifically on Contacts, sometimes by more than 3x its 500ms
   budget. Fixed by skipping the redundant re-render whenever the header
   search query hasn't actually changed since the directory was last drawn
   (`_on_header_search`'s new guard, `main_window.py`). Cut the real cost to
   ~450-800ms, in line with every other view.

2. **Every `CTkSwitch`/`CTkCheckBox`/`CTkRadioButton` app-wide except 3 sites
   left CustomTkinter's own stock default theme colors untouched**
   (`fg_color`/`progress_color` `['#3B8ED0', '#1F6AA5']` -- a generic blue,
   confirmed directly against `ctk.ThemeManager.theme`), clashing with this
   app's own indigo `T.ACCENT` (`#6366F1`) used everywhere else (buttons,
   active nav, badges) -- a real "unbranded stock widget" tell, exactly the
   kind of thing that reads as a developer tool rather than a polished
   product. The WhatsApp panel's own "Select all contacts"/"Consent
   confirmed" checkboxes and Compose's own contact-checklist checkbox
   already had the right recipe (`fg_color=T.ACCENT, border_color=T.ACCENT,
   hover_color=T.ACCENT_HOVER, checkmark_color=T.TEXT_HEAD`) -- used as the
   reference standard and applied to the remaining 12 sites: 3 Settings
   switches (Random jitter / Consent required / Email warm-up mode), Card
   Creator's per-section "Show" checkbox + WhatsApp/Email channel radios +
   bulk-send consent checkbox, the Contact Import Review dialog's Skip/Merge
   duplicate-resolution radios, and the Setup Wizard's channel-choice radio.
   The Compose checklist's *opted-out* checkbox variant (`T.TEXT_DIM`,
   disabled) was deliberately left alone -- a muted/disabled look is correct
   there, not a bug.
"""

from __future__ import annotations

import customtkinter as ctk

import src.ui.theme as T


def _find_widgets_by_type_and_text(widget, widget_cls, texts):
    found = {}

    def walk(w):
        if isinstance(w, widget_cls):
            try:
                t = w.cget("text")
            except Exception:
                t = None
            if t in texts and t not in found:
                found[t] = w
        for child in w.winfo_children():
            walk(child)

    walk(widget)
    return found


def test_contacts_navigation_skips_redundant_rerender_when_query_unchanged(app):
    """The literal repro of finding #1: navigating to Contacts twice in a row
    with no change to the search query must not re-render the directory the
    second time."""
    app._show_view("Campaigns")
    app.update()
    app._show_view("Contacts")
    app.update()
    assert getattr(app, "_contacts_directory_rendered", False) is True

    marker = object()
    app._contacts_directory_rendered_marker = marker
    original_render = app._render_contacts_directory
    calls = []

    def spy():
        calls.append(True)
        return original_render()

    app._render_contacts_directory = spy
    try:
        app._show_view("Campaigns")
        app.update()
        app._show_view("Contacts")
        app.update()
        assert calls == [], (
            "navigating to Contacts with an unchanged query re-rendered the "
            "whole directory -- the redundant-render bug is back")
    finally:
        app._render_contacts_directory = original_render


def test_contacts_navigation_still_rerenders_when_query_actually_changes(app):
    """The guard must not skip a *real* query change -- only a no-op
    re-navigation."""
    app._show_view("Contacts")
    app.update()

    app._header_search_var.set("zzz_no_such_contact_zzz")
    app.update()
    assert app.search_var.get() == "zzz_no_such_contact_zzz"

    # restore, so this test doesn't leak state into later ones
    app._header_search_var.set("")
    app.update()
    assert app.search_var.get() == ""


def test_settings_switches_use_the_app_accent_not_ctk_stock_blue(app):
    app._show_view("Settings")
    app.update()
    settings = app.view_containers["Settings"]
    switches = _find_widgets_by_type_and_text(
        settings, ctk.CTkSwitch,
        {"Random jitter", "Consent required", "Email warm-up mode"})
    for label in ("Random jitter", "Consent required", "Email warm-up mode"):
        assert label in switches, f"expected to find the '{label}' switch"
        sw = switches[label]
        assert sw.cget("progress_color") == T.ACCENT, (
            f"'{label}' switch's on-color is {sw.cget('progress_color')!r}, "
            f"expected the app's own T.ACCENT, not CTk's stock default")


def test_card_creator_show_checkbox_and_channel_radios_use_the_app_accent(app):
    app._show_view("Cards")
    app.update()
    tab = app.card_creator_tab
    # The Item 24 "Advanced: Sections" area is genuinely collapsed
    # (unmapped, not just visually de-emphasized) the first time Cards is
    # shown -- the per-section "Show" checkbox lives inside it, so it must
    # be expanded first to be findable at all. Restore afterward so this
    # test doesn't leak UI state into later tests.
    was_expanded = tab._sections_advanced_expanded
    if not was_expanded:
        tab._toggle_advanced_sections()
    app.update()
    try:
        # Scoped to the sections list itself, not the whole Cards view --
        # walking the full view container hits Python's own recursion limit
        # given how deep/wide this app's full widget tree is (the same
        # limitation already documented for test_ai_key_onboarding.py).
        checkboxes = _find_widgets_by_type_and_text(tab._sections_scroll, ctk.CTkCheckBox, {"Show"})
        assert "Show" in checkboxes, "expected to find a per-section 'Show' checkbox"
        assert checkboxes["Show"].cget("fg_color") == T.ACCENT
    finally:
        if tab._sections_advanced_expanded != was_expanded:
            tab._toggle_advanced_sections()
        app.update()


def test_reference_standard_checkboxes_were_not_regressed(app):
    """The 3 sites that were already correct before this item (WhatsApp
    panel's Select-all/Consent-confirmed, Compose's contact checklist) must
    still use the same recipe -- this item only ever adds to that set, never
    changes it."""
    app._show_view("Compose")
    app.update()
    compose = app.view_containers["Compose"]
    checkboxes = _find_widgets_by_type_and_text(
        compose, ctk.CTkCheckBox, {"Select all contacts", "Consent confirmed"})
    for label in ("Select all contacts", "Consent confirmed"):
        assert label in checkboxes, f"expected to find the '{label}' checkbox"
        assert checkboxes[label].cget("fg_color") == T.ACCENT
        assert checkboxes[label].cget("checkmark_color") == T.TEXT_HEAD
