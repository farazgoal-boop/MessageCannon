"""Minimal hover tooltip — no third-party CTkToolTip dependency. Bind to any
widget (usually a field's label) so non-technical users get a plain-language
explanation of jargon (SMTP, jitter, API key, etc.) without cluttering the
layout with a permanent help block.
"""

from __future__ import annotations

import customtkinter as ctk

from . import theme as T


class Tooltip:
    def __init__(self, widget, text: str, delay_ms: int = 450):
        self.widget = widget
        self.text = text
        self.delay_ms = delay_ms
        self._after_id = None
        self._tip = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<Button-1>", self._hide, add="+")

    def _schedule(self, _event=None) -> None:
        self._cancel()
        self._after_id = self.widget.after(self.delay_ms, self._show)

    def _cancel(self) -> None:
        if self._after_id:
            try:
                self.widget.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None

    def _show(self) -> None:
        if self._tip is not None:
            return
        try:
            x = self.widget.winfo_rootx() + 4
            y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
        except Exception:
            return
        tip = ctk.CTkToplevel(self.widget)
        tip.overrideredirect(True)
        tip.attributes("-topmost", True)
        frame = ctk.CTkFrame(tip, fg_color=T.BG_INNER, corner_radius=6,
                              border_width=1, border_color=T.BG_BORDER)
        frame.pack()
        ctk.CTkLabel(frame, text=self.text, text_color=T.TEXT_HEAD,
                     font=ctk.CTkFont(size=11), wraplength=260, justify="left").pack(
            padx=10, pady=6)
        tip.update_idletasks()
        tip.geometry(f"+{x}+{y}")
        self._tip = tip

    def _hide(self, _event=None) -> None:
        self._cancel()
        if self._tip is not None:
            try:
                self._tip.destroy()
            except Exception:
                pass
            self._tip = None


def add_tooltip(widget, text: str, delay_ms: int = 450) -> Tooltip:
    return Tooltip(widget, text, delay_ms)
