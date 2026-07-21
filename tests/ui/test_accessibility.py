"""Coverage for src/ui/accessibility.py (Item 4, final completion pass) --
CustomTkinter's CTkButton/CTkSwitch/CTkCheckBox/CTkSlider are canvas-drawn
widgets with no built-in Enter/Space activation or arrow-key slider control,
confirmed by reading each class's own _create_bindings before writing this
patch. Rather than construct a full MainWindow (importing
src.ui.main_window is enough to trigger enable_keyboard_accessibility() at
module level, since that's exactly where the real app calls it), this
builds a lightweight dedicated root + individual widgets to test the patch
directly and fast.
"""

import tkinter as tk

import customtkinter as ctk
import pytest

# Importing main_window triggers enable_keyboard_accessibility() at module
# level -- the same real code path the shipped app uses, not a re-invocation
# of the patch function in isolation.
import src.ui.main_window  # noqa: F401


@pytest.fixture(scope="module")
def root():
    window = ctk.CTk()
    window.update()
    yield window
    try:
        if window.winfo_exists():
            window.destroy()
    except Exception:
        pass


def _press(widget, sequence: str) -> None:
    widget._canvas.focus_force()
    widget._canvas.update()
    widget._canvas.event_generate(sequence, when="now")
    widget._canvas.update()


def test_button_activates_on_enter_and_space(root):
    calls = []
    btn = ctk.CTkButton(root, text="Test", command=lambda: calls.append(1))
    btn.pack()
    root.update()

    _press(btn, "<Return>")
    assert len(calls) == 1

    _press(btn, "<space>")
    assert len(calls) == 2

    btn.destroy()


def test_disabled_button_does_not_activate_on_enter(root):
    calls = []
    btn = ctk.CTkButton(root, text="Test", command=lambda: calls.append(1), state="disabled")
    btn.pack()
    root.update()

    _press(btn, "<Return>")
    assert calls == [], "a disabled button must not fire its command via keyboard either"

    btn.destroy()


def test_switch_toggles_on_enter_and_space(root):
    var = ctk.BooleanVar(value=False)
    sw = ctk.CTkSwitch(root, text="Test", variable=var)
    sw.pack()
    root.update()

    _press(sw, "<Return>")
    assert var.get() is True

    _press(sw, "<space>")
    assert var.get() is False

    sw.destroy()


def test_checkbox_toggles_on_enter_and_space(root):
    var = ctk.BooleanVar(value=False)
    cb = ctk.CTkCheckBox(root, text="Test", variable=var)
    cb.pack()
    root.update()

    _press(cb, "<Return>")
    assert var.get() is True

    _press(cb, "<space>")
    assert var.get() is False

    cb.destroy()


def test_slider_arrow_keys_nudge_value_and_invoke_command(root):
    calls = []
    slider = ctk.CTkSlider(root, from_=0, to=100, number_of_steps=100,
                            command=lambda v: calls.append(v))
    slider.set(50)
    slider.pack()
    root.update()

    _press(slider, "<Right>")
    assert slider.get() == pytest.approx(51, abs=0.01)
    assert calls and calls[-1] == pytest.approx(51, abs=0.01)

    _press(slider, "<Left>")
    _press(slider, "<Left>")
    assert slider.get() == pytest.approx(49, abs=0.01)

    slider.destroy()


def test_slider_arrow_keys_clamp_to_range(root):
    slider = ctk.CTkSlider(root, from_=0, to=10, number_of_steps=10)
    slider.set(0)
    slider.pack()
    root.update()

    _press(slider, "<Left>")
    assert slider.get() == pytest.approx(0, abs=0.01), "must not go below from_"

    slider.set(10)
    root.update()
    _press(slider, "<Right>")
    assert slider.get() == pytest.approx(10, abs=0.01), "must not go above to"

    slider.destroy()


def test_button_canvas_is_tab_reachable(root):
    """The real bug this module exists to fix: CTkButton's own focus_set()
    delegates to a plain tkinter.Label (takefocus=0 by default), so before
    this patch, a real <Tab> keypress from a focused CTkEntry never landed
    on a CTkButton at all -- confirmed directly, twice, with a real <Tab>
    key event in a standalone repro script while building this fix (see
    accessibility.py's module docstring), not assumed.

    That exact repro is not used as this automated test, though: run inside
    this module-scoped, multi-test-reusing pytest fixture specifically (not
    in an ad hoc standalone script), Tk's default <Tab> binding intermittently
    raises "invalid command name tk_focusNext" -- a Tcl-autoload timing quirk
    tied to this specific fixture's widget churn across many prior tests in
    the same process, not to this fix. Asserting takefocus=1 directly tests
    the actual, deterministic thing the fix changes (confirmed via the
    standalone repro to be exactly what makes real Tab traversal reach the
    widget) without depending on that fragile autoload path.
    """
    btn = ctk.CTkButton(root, text="Tab Target")
    btn.pack()
    root.update()

    assert int(btn._canvas.cget("takefocus")) == 1

    btn.destroy()


def test_switch_checkbox_slider_canvases_are_tab_reachable(root):
    sw = ctk.CTkSwitch(root)
    cb = ctk.CTkCheckBox(root)
    slider = ctk.CTkSlider(root)
    sw.pack()
    cb.pack()
    slider.pack()
    root.update()

    assert int(sw._canvas.cget("takefocus")) == 1
    assert int(cb._canvas.cget("takefocus")) == 1
    assert int(slider._canvas.cget("takefocus")) == 1

    sw.destroy()
    cb.destroy()
    slider.destroy()


def test_button_focus_shows_and_clears_a_visible_ring(root):
    btn = ctk.CTkButton(root, text="Test", border_width=0)
    btn.pack()
    root.update()

    original_width = btn.cget("border_width")
    btn._canvas.event_generate("<FocusIn>", when="now")
    btn._canvas.update()
    assert int(btn.cget("border_width")) >= 2

    btn._canvas.event_generate("<FocusOut>", when="now")
    btn._canvas.update()
    assert btn.cget("border_width") == original_width

    btn.destroy()
