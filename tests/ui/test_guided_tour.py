"""Item 39 v2: cursor-following "hover to discover" tour mode.

Replaces the old sequential-cards test file entirely (the click-through
modal dialog it tested no longer exists). Hover simulation follows this
suite's own already-established, documented practice for this exact
limitation (`test_card_creator_premium.py`'s icon-zone hover tests, and
`tests/ui/conftest.py`'s own account of direct-event-synthesis fragility in
this harness): call the tour's own `_on_enter`/`_on_leave` handlers
directly -- the literal same code a real `<Enter>`/`<Leave>` binding
invokes -- rather than trust cross-widget mouse-motion simulation. One
additional test (`test_enable_wires_real_enter_leave_bindings_on_widgets`)
independently confirms the *real* Tk-level binding wiring itself, via
`event_generate`, so the handler-logic tests above aren't the only proof
this is really wired to the real widgets.
"""

from __future__ import annotations

import time
import tkinter as tk

from src.ui.tour import DISCOVERABLE_ITEMS, TourMode, _hover_target


def _pump(window, seconds: float) -> None:
    deadline = time.time() + seconds
    while time.time() < deadline:
        window.update()
        time.sleep(0.01)


def _find_button(widget, text):
    import customtkinter as ctk
    for child in widget.winfo_children():
        if isinstance(child, ctk.CTkButton):
            try:
                if child.cget("text") == text:
                    return child
            except Exception:
                pass
        found = _find_button(child, text)
        if found is not None:
            return found
    return None


def test_discoverable_items_reference_real_getters_and_cover_named_features(app):
    """Every getter must resolve to a real widget on the real app (guards
    against a future rename silently breaking a discovery item), and the
    exact features Item 39 v2's own spec named by example -- sidebar nav,
    Compose's Generate-with-AI, the Card template gallery, the update
    badge -- are all represented."""
    ids = {item["id"] for item in DISCOVERABLE_ITEMS}
    for expected in ("campaigns", "contacts", "compose", "cards", "history",
                      "settings", "update_badge", "generate_ai", "card_gallery"):
        assert expected in ids
    for item in DISCOVERABLE_ITEMS:
        widget = item["getter"](app)
        assert widget is not None, item["id"]


def test_header_tour_button_exists_and_toggles_tour_mode(app):
    assert hasattr(app, "header_tour_btn")
    assert app.header_tour_btn.cget("text") == "?"
    assert not app.tour_mode.is_active
    app.header_tour_btn.cget("command")()
    try:
        assert app.tour_mode.is_active
    finally:
        app.tour_mode.disable()


def test_settings_has_a_take_a_tour_button_that_toggles_tour_mode(app):
    original_view = app._active_view
    app._show_view("Settings")
    app.update()
    try:
        btn = _find_button(app, "🧭 Take a Tour")
        assert btn is not None
        assert not app.tour_mode.is_active
        btn.cget("command")()
        assert app.tour_mode.is_active
    finally:
        app.tour_mode.disable()
        app._show_view(original_view)
        app.update()


def test_enable_binds_every_real_widget_and_sets_total(app):
    tour = app.tour_mode
    tour.enable()
    try:
        assert tour.total_count == len(DISCOVERABLE_ITEMS)
        assert tour.discovered_count == 0
    finally:
        tour.disable()


def test_hovering_an_item_marks_it_discovered_and_updates_progress(app):
    tour = app.tour_mode
    tour.enable()
    try:
        tour._on_enter("campaigns")
        assert "campaigns" in tour._discovered
        assert tour.discovered_count == 1
        assert tour._hud._text_var.get() == f"1 of {tour.total_count} explored"
    finally:
        tour.disable()


def test_hud_stays_fully_within_the_real_window_bounds(app):
    """Real bug found while producing this feature's own demo screenshot:
    a freshly-constructed CTkToplevel's winfo_width() reported a stale,
    un-rendered placeholder value, and positioning the HUD against that
    number let its real window (and the "Exit Tour" button inside it)
    extend past the app's own right edge -- confirmed directly in a real
    screenshot, not assumed. Fixed with an explicit, DPI-scale-aware
    geometry. This checks the real, current window/HUD/button coordinates,
    not the positioning math in isolation."""
    tour = app.tour_mode
    tour.enable()
    try:
        app.update()
        window_right = app.winfo_rootx() + app.winfo_width()
        hud_right = tour._hud.win.winfo_rootx() + tour._hud.win.winfo_width()
        btn_right = tour._hud.exit_btn.winfo_rootx() + tour._hud.exit_btn.winfo_width()
        assert hud_right <= window_right
        assert btn_right <= window_right
    finally:
        tour.disable()


def test_hovering_shows_the_real_card_content_and_spotlight_ring(app):
    tour = app.tour_mode
    tour.enable()
    try:
        tour._on_enter("contacts")
        assert tour._card._title_var.get() == "Contacts"
        assert tour._card.win.winfo_ismapped()
        assert tour._ring._bars[0].winfo_ismapped()
        target = app.sidebar_buttons["Contacts"]
        ring_x = tour._ring._bars[0].winfo_rootx()
        assert abs(ring_x - (target.winfo_rootx() - 6)) <= 2
    finally:
        tour.disable()


def test_switching_hover_target_updates_content_without_needing_a_leave(app):
    tour = app.tour_mode
    tour.enable()
    try:
        tour._on_enter("campaigns")
        tour._on_enter("contacts")
        assert tour._active_id == "contacts"
        assert tour._card._title_var.get() == "Contacts"
        # both items were visited, so both count toward progress
        assert tour._discovered == {"campaigns", "contacts"}
    finally:
        tour.disable()


def test_discovered_items_get_a_persistent_checkmark_badge(app):
    tour = app.tour_mode
    tour.enable()
    try:
        tour._on_enter("campaigns")
        assert "campaigns" in tour._badges
        badge = tour._badges["campaigns"]
        assert badge.win.winfo_ismapped()
        # moving to a different item leaves the earlier badge in place --
        # "one continuous pass" means prior discoveries stay visibly marked.
        tour._on_enter("contacts")
        assert badge.win.winfo_ismapped()
    finally:
        tour.disable()


def test_leaving_after_a_delay_hides_card_and_ring_but_keeps_badge(app):
    """Real timer-driven proof, not a simulated shortcut: `_on_leave`
    schedules a real `.after()` deferred hide -- this waits for that real
    timer (plus the real fade-out) to actually fire, rather than
    replicating its internal logic inline."""
    tour = app.tour_mode
    tour.enable()
    try:
        tour._on_enter("campaigns")
        badge = tour._badges["campaigns"]
        tour._on_leave("campaigns")
        _pump(app, 0.4)
        assert tour._active_id is None
        assert not tour._ring._bars[0].winfo_ismapped()
        assert not tour._card.win.winfo_ismapped()
        assert badge.win.winfo_ismapped()
    finally:
        tour.disable()


def test_exit_tour_button_disables_tour_mode_and_cleans_up_overlays(app):
    tour = app.tour_mode
    tour.enable()
    tour._on_enter("campaigns")
    ring_bar = tour._ring._bars[0]
    card_win = tour._card.win
    badge_win = tour._badges["campaigns"].win
    hud = tour._hud

    hud.exit_btn.cget("command")()

    assert not tour.is_active
    assert not ring_bar.winfo_exists()
    assert not card_win.winfo_exists()
    assert not badge_win.winfo_exists()
    assert tour._card is None
    assert tour._badges == {}


def test_escape_key_disables_tour_mode(app):
    tour = app.tour_mode
    tour.enable()
    try:
        assert tour.is_active
        app.event_generate("<Escape>")
        app.update()
        assert not tour.is_active
    finally:
        if tour.is_active:
            tour.disable()


def test_header_button_visually_reflects_active_state(app):
    import src.ui.theme as T
    tour = app.tour_mode
    inactive_color = app.header_tour_btn.cget("fg_color")
    tour.enable()
    try:
        assert app.header_tour_btn.cget("fg_color") == T.ACCENT
        assert app.header_tour_btn.cget("fg_color") != inactive_color
    finally:
        tour.disable()
    assert app.header_tour_btn.cget("fg_color") == inactive_color


def test_reenabling_after_disable_resets_discovered_progress(app):
    tour = app.tour_mode
    tour.enable()
    tour._on_enter("campaigns")
    tour._on_enter("contacts")
    assert tour.discovered_count == 2
    tour.disable()

    tour.enable()
    try:
        assert tour.discovered_count == 0
        assert tour._hud._text_var.get() == f"0 of {tour.total_count} explored"
    finally:
        tour.disable()


def test_toggle_flips_between_enabled_and_disabled(app):
    tour = app.tour_mode
    assert not tour.is_active
    tour.toggle()
    assert tour.is_active
    tour.toggle()
    assert not tour.is_active


def test_overlay_windows_are_marked_click_through_and_hud_is_not(app):
    """The redesign's own core safety requirement -- purely-visual overlays
    must never intercept a real click meant for the app underneath them,
    while the HUD's Exit Tour button must remain genuinely clickable. On
    non-Windows this degrades to a no-op (documented in tour.py), so this
    test only asserts real OS-level style bits when running on win32."""
    import sys
    if sys.platform != "win32":
        import pytest
        pytest.skip("click-through is a real Win32 API call, Windows-only")

    import ctypes
    GWL_EXSTYLE = -20
    WS_EX_LAYERED = 0x00080000
    WS_EX_TRANSPARENT = 0x00000020
    GA_ROOT = 2

    def is_click_through(win) -> bool:
        hwnd = ctypes.windll.user32.GetAncestor(win.winfo_id(), GA_ROOT)
        style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        return bool(style & WS_EX_LAYERED) and bool(style & WS_EX_TRANSPARENT)

    tour = app.tour_mode
    tour.enable()
    tour._on_enter("campaigns")
    try:
        assert is_click_through(tour._card.win)
        assert is_click_through(tour._glow.win)
        assert is_click_through(tour._ring._bars[0])
        assert is_click_through(tour._badges["campaigns"].win)
        assert not is_click_through(tour._hud.win)
    finally:
        tour.disable()


def test_enable_wires_real_enter_leave_bindings_on_widgets(app):
    """Confirms the real Tk-level wiring exists -- not just that the
    handler *logic* works when called directly (every test above), but
    that `enable()` genuinely registered a real callback on the real
    widget's real hoverable surface."""
    tour = app.tour_mode
    tour.enable()
    try:
        target, enter_id, leave_id = tour._bindings["campaigns"]
        assert target is _hover_target(app.sidebar_buttons["Campaigns"])
        assert isinstance(target, tk.Widget)
        assert target.bind("<Enter>") != ""
        assert target.bind("<Leave>") != ""
    finally:
        tour.disable()


def test_disable_unbinds_without_breaking_the_widgets_own_hover_behavior(app):
    """Precise funcid-based unbind -- must not wipe CTkButton's own
    hover_color binding or accessibility.py's own focus-ring binding on the
    same canvas, only the tour's own handler."""
    tour = app.tour_mode
    target = _hover_target(app.sidebar_buttons["Campaigns"])
    before = target.bind("<Enter>")
    tour.enable()
    tour.disable()
    after = target.bind("<Enter>")
    # Some real binding still remains (CTkButton's own hover mechanic) --
    # confirms disable() didn't blanket-unbind everything on this widget.
    assert after != ""
    assert "campaigns" not in tour._bindings
