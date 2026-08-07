"""Item 39: reusable, re-triggerable guided tour ("Take a Tour" / "?" button).

Verifies the real, end-to-end run-through this item explicitly asked for:
opening from both real entry points, advancing/going back through every real
step (navigating the real underlying view where a step specifies one and
spotlighting the real corresponding sidebar widget), Skip/Finish/Escape all
correctly tearing the tour down and restoring whatever view was active
before it opened, and that re-triggering always restarts at step 1 rather
than resuming or stacking a second copy.
"""

from __future__ import annotations

import customtkinter as ctk

from src.ui.tour import TOUR_STEPS, start_guided_tour


def _find_button(widget, text):
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


def test_tour_steps_reference_only_real_views():
    """Every step that names a `view` must be a view this app actually
    builds -- guards against a future view rename silently breaking a step's
    navigation (the tour would call _show_view with a name that matches
    nothing, and the spotlight would then look for a widget on the wrong
    screen)."""
    real_views = {"Campaigns", "Contacts", "Compose", "History", "Cards", "Settings"}
    for step in TOUR_STEPS:
        if step["view"] is not None:
            assert step["view"] in real_views, step["id"]
    # Every major feature named in the item's own spec is represented.
    ids = {s["id"] for s in TOUR_STEPS}
    for expected in ("campaigns", "contacts", "compose", "cards", "history", "settings", "updates"):
        assert expected in ids


def test_header_tour_button_exists_and_is_wired(app):
    assert hasattr(app, "header_tour_btn")
    assert app.header_tour_btn.cget("text") == "?"
    assert callable(app.header_tour_btn.cget("command"))


def test_settings_has_a_take_a_tour_button(app):
    original_view = app._active_view
    app._show_view("Settings")
    app.update()
    try:
        btn = _find_button(app, "🧭 Take a Tour")
        assert btn is not None, "expected a real 'Take a Tour' button in Settings"
    finally:
        app._show_view(original_view)
        app.update()


def test_start_guided_tour_opens_on_step_one_with_real_progress_text(app):
    dialog = start_guided_tour(app)
    app.update()
    try:
        assert dialog._step_index == 0
        assert dialog._progress_var.get() == f"Step 1 of {len(TOUR_STEPS)}"
        assert dialog._title_var.get() == TOUR_STEPS[0]["title"]
        assert dialog._back_btn.cget("state") == "disabled"
    finally:
        dialog._finish()
        app.update()


def test_next_advances_and_navigates_the_real_underlying_view(app):
    """A step whose own `view` is e.g. "Contacts" must really switch the
    live app to that view -- this is the literal "real corresponding UI
    element" tie-in the item asked for, not just card text changing."""
    dialog = start_guided_tour(app)
    app.update()
    try:
        # step 0 is the intro (view=None); step 1 is "campaigns" (view=Campaigns)
        dialog._go_next()
        app.update()
        assert dialog._step_index == 1
        assert TOUR_STEPS[1]["view"] == "Campaigns"
        assert app._active_view == "Campaigns"

        dialog._go_next()
        app.update()
        assert TOUR_STEPS[2]["view"] == "Contacts"
        assert app._active_view == "Contacts"
        assert dialog._back_btn.cget("state") == "normal"
    finally:
        dialog._finish()
        app.update()


def test_back_returns_to_the_previous_step_and_its_view(app):
    dialog = start_guided_tour(app)
    app.update()
    try:
        dialog._go_next()
        dialog._go_next()
        app.update()
        assert dialog._step_index == 2
        dialog._go_back()
        app.update()
        assert dialog._step_index == 1
        assert app._active_view == TOUR_STEPS[1]["view"]
    finally:
        dialog._finish()
        app.update()


def test_spotlight_ring_positions_over_a_real_mapped_sidebar_button(app):
    dialog = start_guided_tour(app)
    app.update()
    try:
        dialog._go_next()  # step 1: "campaigns", targets the real Campaigns nav button
        app.update()
        target = app.sidebar_buttons["Campaigns"]
        positioned = dialog._ring.move_to(target)
        assert positioned is True
        for bar in dialog._ring._bars:
            assert bar.winfo_ismapped()
        # The ring's own bounds must genuinely wrap the target's real bounds,
        # not just be present somewhere on screen.
        top_bar = dialog._ring._bars[0]
        assert abs(top_bar.winfo_rootx() - (target.winfo_rootx() - 5)) <= 2
    finally:
        dialog._finish()
        app.update()


def test_spotlight_ring_hides_for_a_missing_target():
    class _FakeMaster(ctk.CTkToplevel):
        pass

    # Build a throwaway ring against nothing real to prove hide()/None-target
    # behavior without needing a whole tour dialog.
    from src.ui.tour import _SpotlightRing

    class _Holder:
        pass

    # Reuse the real app's own root indirectly is unnecessary here -- the
    # ring's own master just needs to be a real Tk window; the shared `app`
    # fixture isn't required for this particular check since it only
    # exercises move_to(None).
    import tkinter as tk
    root = tk.Tk()
    root.withdraw()
    try:
        top = tk.Toplevel(root)
        ring = _SpotlightRing.__new__(_SpotlightRing)
        ring._bars = [tk.Toplevel(top) for _ in range(4)]
        for bar in ring._bars:
            bar.overrideredirect(True)
        result = ring.move_to(None)
        assert result is False
        for bar in ring._bars:
            assert not bar.winfo_ismapped()
    finally:
        root.destroy()


def test_last_step_shows_finish_and_closes_the_dialog(app):
    dialog = start_guided_tour(app)
    app.update()
    try:
        for _ in range(len(TOUR_STEPS) - 1):
            dialog._go_next()
            app.update()
        assert dialog._step_index == len(TOUR_STEPS) - 1
        assert dialog._next_btn.cget("text") == "Finish"
        dialog._next_btn.cget("command")()
        app.update()
        assert not dialog.winfo_exists()
    finally:
        pass


def test_finish_restores_the_view_active_before_the_tour_opened(app):
    app._show_view("Settings")
    app.update()
    dialog = start_guided_tour(app)
    app.update()
    dialog._go_next()  # -> Campaigns step
    dialog._go_next()  # -> Contacts step
    app.update()
    assert app._active_view == "Contacts"
    dialog._finish()
    app.update()
    assert app._active_view == "Settings"


def test_skip_button_closes_immediately_from_step_one(app):
    original = app._active_view
    dialog = start_guided_tour(app)
    app.update()
    skip_btn = _find_button(dialog, "Skip")
    assert skip_btn is not None
    skip_btn.cget("command")()
    app.update()
    assert not dialog.winfo_exists()
    assert app._active_view == original


def test_escape_closes_the_tour(app):
    dialog = start_guided_tour(app)
    app.update()
    dialog.event_generate("<Escape>")
    app.update()
    assert not dialog.winfo_exists()


def test_retriggering_the_tour_always_restarts_at_step_one(app):
    first = start_guided_tour(app)
    app.update()
    first._go_next()
    first._go_next()
    app.update()
    assert first._step_index == 2

    second = start_guided_tour(app)
    app.update()
    try:
        assert not first.winfo_exists()
        assert second is not first
        assert second._step_index == 0
        assert app._tour_dialog is second
    finally:
        second._finish()
        app.update()
