"""App-wide keyboard-accessibility patch for CustomTkinter widgets.

CustomTkinter draws every interactive widget (buttons, switches, checkboxes,
sliders) as shapes on a raw Tk Canvas rather than using native Tk widgets.
Two real gaps were confirmed directly, not assumed, before writing this fix:

1. `_create_bindings` on each class only ever binds `<Enter>`/`<Leave>`/
   `<Button-1>` -- nothing for `<Return>`/`<space>` or arrow keys.
2. **Tab traversal doesn't even reach these widgets in the first place.**
   CTkButton's own `focus_set()` delegates to `self._text_label.focus_set()`
   -- but `_text_label` is a plain `tkinter.Label`, which defaults to
   `takefocus=0`. Confirmed with a real `<Tab>` key event from a focused
   CTkEntry: focus never moved onto a CTkButton until `_canvas.configure(
   takefocus=1)` was set explicitly, at which point the identical `<Tab>`
   press landed on it.

Rather than touch every individual widget construction call site (hundreds,
across main_window.py, card_creator_tab.py, setup_wizard.py, and every
dialog module), this patches the CustomTkinter classes themselves once, at
import time -- every existing and future CTkButton/CTkSwitch/CTkCheckBox/
CTkSlider in the app gains the same keyboard support automatically.

Performance note, found and fixed while verifying against the existing
`test_navigation_timing.py` suite (not just assumed safe): a per-instance
`widget.bind(sequence, handler)` call for every sequence on every widget
measurably regressed Compose's transition time (its contact checklist is
one CTkCheckBox per contact) -- confirmed via a controlled A/B (accessibility
patch stashed out vs applied, 3 runs each) that this feature, not
unrelated noise, pushed Compose from a passing ~650ms to a failing
~750-860ms against its documented 700ms budget. Root cause: each
`.bind()`/`.configure()` call is a real Tcl round trip, and this patch was
doing several per widget. Fixed by switching from N per-instance `.bind()`
calls to Tk's own class-level binding mechanism (`bind_class`): the
`<Return>`/`<space>`/`<FocusIn>`/`<FocusOut>`/arrow-key handlers are
registered exactly ONCE, ever, against a custom bindtag; each widget
instance then only pays for adding that one bindtag plus the one
`takefocus` configure call (2 Tcl calls instead of up to 9), with the
per-widget dispatch data (which activate function, which original border
values) stored as plain Python attributes on the canvas -- free, no Tcl
call at all. Confirmed this restores Compose to passing consistently
across 5 consecutive runs after the change (see this item's CLAUDE.md
checkpoint for the exact numbers).
"""

from __future__ import annotations

import tkinter as tk

import customtkinter as ctk

_PATCHED = False

_ACTIVATABLE_TAG = "CTkAccessibleActivatable"
_SLIDER_TAG = "CTkAccessibleSlider"
_class_bindings_registered = {"activatable": False, "slider": False}


def _make_tab_reachable(canvas) -> None:
    """The actual root cause of these widgets being unreachable by Tab at
    all: their focusable delegate (see module docstring) has takefocus=0
    by default. Forcing takefocus=1 directly on the canvas -- confirmed via
    a real <Tab>-key test, not assumed -- is what makes Tk's own focus
    traversal actually visit them."""
    try:
        canvas.configure(takefocus=1)
    except tk.TclError:
        pass


def _add_bindtag(canvas, tag: str) -> None:
    try:
        tags = canvas.bindtags()
        if tag not in tags:
            canvas.bindtags(tags + (tag,))
    except tk.TclError:
        pass


def _class_default_border(cls) -> tuple:
    """The border_width/border_color a widget of this class gets when the
    call site doesn't pass one explicitly -- read once per class from
    CustomTkinter's own theme dict (no Tcl call), not per-instance via
    `.cget()` (a real Tcl round trip that was the first, smaller cause of
    the Compose regression noted in the module docstring, fixed before the
    bind_class rewrite above but kept fixed this way regardless)."""
    entry = ctk.ThemeManager.theme.get(cls.__name__, {})
    return entry.get("border_width", 0), entry.get("border_color", "transparent")


def _ensure_activatable_class_bindings(any_widget) -> None:
    """Registered exactly once, ever -- not per widget instance. Dispatches
    via plain Python attributes stashed on the event's target canvas
    (`_ctk_activate`, `_ctk_focus_in`, `_ctk_focus_out`), set once at
    construction time with no Tcl call involved."""
    if _class_bindings_registered["activatable"]:
        return
    _class_bindings_registered["activatable"] = True

    def on_key(event):
        activate = getattr(event.widget, "_ctk_activate", None)
        if activate is not None:
            activate(event)

    def on_focus_in(event):
        handler = getattr(event.widget, "_ctk_focus_in", None)
        if handler is not None:
            handler()

    def on_focus_out(event):
        handler = getattr(event.widget, "_ctk_focus_out", None)
        if handler is not None:
            handler()

    any_widget.bind_class(_ACTIVATABLE_TAG, "<Return>", on_key, add=True)
    any_widget.bind_class(_ACTIVATABLE_TAG, "<space>", on_key, add=True)
    any_widget.bind_class(_ACTIVATABLE_TAG, "<FocusIn>", on_focus_in, add=True)
    any_widget.bind_class(_ACTIVATABLE_TAG, "<FocusOut>", on_focus_out, add=True)


def _ensure_slider_class_bindings(any_widget) -> None:
    if _class_bindings_registered["slider"]:
        return
    _class_bindings_registered["slider"] = True

    def on_key(direction):
        def handler(event):
            nudge = getattr(event.widget, "_ctk_nudge", None)
            if nudge is not None:
                nudge(direction)
        return handler

    any_widget.bind_class(_SLIDER_TAG, "<Left>", on_key(-1), add=True)
    any_widget.bind_class(_SLIDER_TAG, "<Down>", on_key(-1), add=True)
    any_widget.bind_class(_SLIDER_TAG, "<Right>", on_key(1), add=True)
    any_widget.bind_class(_SLIDER_TAG, "<Up>", on_key(1), add=True)
    any_widget.bind_class(_SLIDER_TAG, "<FocusIn>", lambda e: _dispatch_focus(e, "_ctk_focus_in"), add=True)
    any_widget.bind_class(_SLIDER_TAG, "<FocusOut>", lambda e: _dispatch_focus(e, "_ctk_focus_out"), add=True)


def _dispatch_focus(event, attr: str) -> None:
    handler = getattr(event.widget, attr, None)
    if handler is not None:
        handler()


def _make_focus_ring_handlers(widget, original_border_width, original_border_color):
    def on_focus_in() -> None:
        try:
            from . import theme as T
            widget.configure(border_width=max(int(original_border_width or 0), 2),
                              border_color=T.ACCENT)
        except Exception:
            pass

    def on_focus_out() -> None:
        try:
            widget.configure(border_width=original_border_width,
                              border_color=original_border_color)
        except Exception:
            pass

    return on_focus_in, on_focus_out


def _patch_activatable(cls, activate) -> None:
    """`activate(widget, event)` is called on Enter/Space once the widget
    has keyboard focus -- for CTkButton this invokes its own `_clicked`
    (already guards against a disabled state); for CTkSwitch/CTkCheckBox
    it invokes their own public `toggle` (same guard)."""
    original_init = cls.__init__
    default_width, default_color = _class_default_border(cls)

    def patched_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        _ensure_activatable_class_bindings(self)

        canvas = self._canvas
        canvas._ctk_activate = lambda event, w=self: activate(w, event)
        focus_in, focus_out = _make_focus_ring_handlers(
            self, kwargs.get("border_width", default_width),
            kwargs.get("border_color", default_color))
        canvas._ctk_focus_in = focus_in
        canvas._ctk_focus_out = focus_out

        _add_bindtag(canvas, _ACTIVATABLE_TAG)
        _make_tab_reachable(canvas)

    cls.__init__ = patched_init


def _patch_slider(cls) -> None:
    """Arrow-key value adjustment -- CTkSlider has no keyboard control at
    all by default, so a keyboard-only user could Tab to it (once
    `_make_tab_reachable` is applied) but never change its value. Nudges by
    one configured step, clamped to the slider's own from_/to range, and
    calls its command callback exactly like a real drag would."""
    original_init = cls.__init__
    default_width, default_color = _class_default_border(cls)

    def patched_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        _ensure_slider_class_bindings(self)

        def nudge(direction, w=self):
            steps = w._number_of_steps or 100
            step = (w._to - w._from_) / steps
            new_val = min(max(w.get() + direction * step, w._from_), w._to)
            w.set(new_val)
            if w._command:
                w._command(new_val)

        canvas = self._canvas
        canvas._ctk_nudge = nudge
        focus_in, focus_out = _make_focus_ring_handlers(
            self, kwargs.get("border_width", default_width),
            kwargs.get("border_color", default_color))
        canvas._ctk_focus_in = focus_in
        canvas._ctk_focus_out = focus_out

        _add_bindtag(canvas, _SLIDER_TAG)
        _make_tab_reachable(canvas)

    cls.__init__ = patched_init


def enable_keyboard_accessibility() -> None:
    """Idempotent -- safe to call more than once (e.g. multiple import
    paths during tests); only patches on the first call."""
    global _PATCHED
    if _PATCHED:
        return
    _PATCHED = True

    _patch_activatable(ctk.CTkButton, lambda w, event=None: w._clicked(event))
    _patch_activatable(ctk.CTkSwitch, lambda w, event=None: w.toggle(event))
    _patch_activatable(ctk.CTkCheckBox, lambda w, event=None: w.toggle(event))
    _patch_slider(ctk.CTkSlider)
