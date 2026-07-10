"""Lightweight, non-blocking toast notifications — replaces messagebox.showinfo
for simple one-way "it worked" confirmations (saved/exported/activated) so the
user isn't forced to click "OK" on something that doesn't need a decision.
Destructive/decision-requiring dialogs stay as real modal dialogs — see
send_dialogs.py and confirm_dialogs.py.
"""

from __future__ import annotations

import customtkinter as ctk

from . import theme as T

_KIND_STYLE = {
    "success": ("✓", T.SUCCESS),
    "error": ("✕", T.DANGER_ON_BADGE),
    "info": ("ℹ", T.ACCENT),
}


class Toast(ctk.CTkToplevel):
    def __init__(self, main_window, message: str, kind: str = "success", duration_ms: int = 2800):
        super().__init__(main_window)
        self._main_window = main_window
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        try:
            self.attributes("-alpha", 0.97)
        except Exception:
            pass

        icon, color = _KIND_STYLE.get(kind, _KIND_STYLE["success"])

        outer = ctk.CTkFrame(self, fg_color=T.BG_SURFACE, corner_radius=10,
                              border_width=1, border_color=T.BG_BORDER)
        outer.pack(fill="both", expand=True)
        outer.grid_columnconfigure(1, weight=1)

        ctk.CTkFrame(outer, fg_color=color, width=4, corner_radius=0).grid(
            row=0, column=0, sticky="ns")
        ctk.CTkLabel(outer, text=icon, text_color=color,
                     font=ctk.CTkFont(size=15, weight="bold")).grid(
            row=0, column=1, padx=(12, 6), pady=12, sticky="w")
        ctk.CTkLabel(outer, text=message, text_color=T.TEXT_HEAD,
                     font=ctk.CTkFont(size=12, weight="bold"),
                     wraplength=320, justify="left").grid(
            row=0, column=2, padx=(0, 16), pady=12, sticky="w")

        self.update_idletasks()
        self._position()
        self.after(duration_ms, self._dismiss)
        self.bind("<Button-1>", lambda _e: self._dismiss())

    def _position(self) -> None:
        mw = self._main_window
        mw.update_idletasks()
        mx, my = mw.winfo_rootx(), mw.winfo_rooty()
        mwidth, mheight = mw.winfo_width(), mw.winfo_height()
        w, h = self.winfo_width(), self.winfo_height()
        x = mx + mwidth - w - 28
        y = my + mheight - h - 28
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _dismiss(self) -> None:
        try:
            self.destroy()
        except Exception:
            pass


def show_toast(main_window, message: str, kind: str = "success", duration_ms: int = 2800) -> None:
    existing = getattr(main_window, "_active_toast", None)
    if existing is not None:
        try:
            existing.destroy()
        except Exception:
            pass
    main_window._active_toast = Toast(main_window, message, kind, duration_ms)
