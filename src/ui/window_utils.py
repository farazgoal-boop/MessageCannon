"""Shared window-centering helpers.

Real bug found via live user testing (Item 7 of the Live Testing Findings
pass): the main window and every dialog in the app called `.geometry(
"WxH")` with no position component, so Tk/the window manager decided where
it landed -- normally near the screen's top-left corner rather than
centered, which reads as sloppy/unpolished. Every dialog now centers on its
parent window (falling back to the screen if the parent has no real
geometry yet, e.g. during very early startup); the main window itself
centers on the screen since it has no parent.

Second, more subtle bug found while writing this fix's own regression test
(`test_dialog_centering.py`'s main-window test failed by ~150px, not a
rounding error): CustomTkinter overrides `.geometry()` to silently multiply
just the width/height component by its own internal per-monitor DPI
scaling factor (e.g. 1.25 at 125% Windows scaling) before handing off to
real Tk -- confirmed by reading `ScalingBaseClass._apply_geometry_scaling`
directly -- but leaves any `+x+y` position component completely
unscaled. A `.geometry("1220x760+350+160")` call therefore renders as a
*real*, physical `1525x950` window still positioned at logical `(350,
160)` -- centering math that computes `x`/`y` from the *requested*
(pre-scale) width/height will always be off by exactly half the scaling
delta.

First fix attempt read back the real size via `winfo_width()`/`winfo_height()`
after a `.geometry(f"{width}x{height}")` + `.update()` round-trip -- worked
for the main window (already mapped, existing event loop) but proved
unreliable for freshly-created `CTkToplevel` dialogs: measured a real,
repeatable case where `winfo_width()` still reported CTk's un-rendered
200x200 placeholder immediately after `update()`, because a brand-new
toplevel's *window-manager*-level configure round-trip isn't guaranteed to
complete within a single `update()` call the way an already-mapped root's
does. Rather than chase WM timing further, switched to the deterministic,
non-timing-dependent option: CustomTkinter already computes and stores this
exact scaling factor internally (`ScalingBaseClass._apply_window_scaling`,
used by its own `.geometry()` override) -- calling it directly gives the
real post-scale size synchronously, with no event-loop race at all. Plain
`tk.Tk()`/`tk.Toplevel` windows (no such method, no scaling applied by
CTk) fall back to the requested size unchanged.
"""

from __future__ import annotations

import tkinter as tk


def _real_dimensions(window: tk.Wm, width: int, height: int) -> tuple[int, int]:
    """Returns the size `window` will actually render at for a
    `width`x`height` request -- CTk-scaled if `window` is a CustomTkinter
    window, unchanged for a plain Tk window."""
    scale = getattr(window, "_apply_window_scaling", None)
    if callable(scale):
        try:
            return scale(width), scale(height)
        except Exception:
            pass
    return width, height


def center_on_screen(window: tk.Wm, width: int, height: int) -> None:
    window.update_idletasks()
    real_w, real_h = _real_dimensions(window, width, height)
    screen_w = window.winfo_screenwidth()
    screen_h = window.winfo_screenheight()
    x = max(0, (screen_w - real_w) // 2)
    y = max(0, (screen_h - real_h) // 2)
    window.geometry(f"{width}x{height}+{x}+{y}")


def center_on_parent(window: tk.Wm, width: int, height: int, parent) -> None:
    """Centers `window` over `parent`'s current position, clamped to stay
    fully on-screen. Falls back to `center_on_screen` if `parent` has no
    usable geometry yet (e.g. width/height still 1px pre-layout)."""
    window.update_idletasks()
    real_w, real_h = _real_dimensions(window, width, height)
    try:
        parent.update_idletasks()
        parent_w = parent.winfo_width()
        parent_h = parent.winfo_height()
        if parent_w > 1 and parent_h > 1:
            x = parent.winfo_x() + (parent_w - real_w) // 2
            y = parent.winfo_y() + (parent_h - real_h) // 2
            screen_w = window.winfo_screenwidth()
            screen_h = window.winfo_screenheight()
            x = min(max(0, x), max(0, screen_w - real_w))
            y = min(max(0, y), max(0, screen_h - real_h))
            window.geometry(f"{width}x{height}+{x}+{y}")
            return
    except Exception:
        pass
    center_on_screen(window, width, height)
