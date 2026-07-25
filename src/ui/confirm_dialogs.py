"""Typed-confirmation dialog for destructive "Danger Zone" actions — a plain
Yes/No dialog is too easy to click through by habit. The user must type an
exact confirmation word before the action button enables.
"""

from __future__ import annotations

import customtkinter as ctk

from . import theme as T
from .window_utils import center_on_parent


class DangerConfirmDialog(ctk.CTkToplevel):
    def __init__(self, main_window, title: str, message: str, confirm_word: str,
                 action_label: str, on_confirm):
        super().__init__(main_window)
        self.on_confirm = on_confirm
        self.confirm_word = confirm_word
        self.title(title)
        center_on_parent(self, 440, 320, main_window)
        self.resizable(False, False)
        self.transient(main_window)
        self.grab_set()
        self.configure(fg_color=T.BG_MAIN)
        self.protocol("WM_DELETE_WINDOW", self.destroy)

        self.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(self, text=f"⚠ {title}", font=ctk.CTkFont(size=17, weight="bold"),
                     text_color=T.DANGER_ON_BADGE).grid(row=0, column=0, padx=24, pady=(22, 8), sticky="w")
        ctk.CTkLabel(self, text=message, text_color=T.TEXT_MUTED, font=ctk.CTkFont(size=12),
                     wraplength=390, justify="left").grid(row=1, column=0, padx=24, pady=(0, 16), sticky="w")

        ctk.CTkLabel(self, text=f'Type "{confirm_word}" to confirm', text_color=T.TEXT_HEAD,
                     font=ctk.CTkFont(size=12, weight="bold")).grid(
            row=2, column=0, padx=24, pady=(0, 6), sticky="w")

        self._entry_var = ctk.StringVar(value="")
        self._entry_var.trace_add("write", lambda *_: self._on_type())
        entry = ctk.CTkEntry(self, textvariable=self._entry_var, fg_color=T.BG_INNER,
                              border_color=T.BG_BORDER, text_color=T.TEXT_HEAD, height=36)
        entry.grid(row=3, column=0, padx=24, pady=(0, 20), sticky="ew")
        entry.focus_set()
        self.bind("<Escape>", lambda _e: self.destroy())
        entry.bind("<Return>", lambda _e: self._confirm() if self._entry_var.get().strip() == self.confirm_word else None)

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=4, column=0, padx=24, pady=(0, 20), sticky="ew")
        footer.grid_columnconfigure(0, weight=1)
        ctk.CTkButton(footer, text="Cancel", width=100, fg_color=T.BADGE_BG,
                      hover_color=T.BG_BORDER, text_color=T.TEXT_HEAD,
                      command=self.destroy).grid(row=0, column=0, sticky="w")
        self._action_btn = ctk.CTkButton(
            footer, text=action_label, height=38, state="disabled",
            fg_color=T.DANGER, hover_color=T.DANGER_HOVER, text_color=T.TEXT_HEAD,
            font=ctk.CTkFont(size=13, weight="bold"), command=self._confirm)
        self._action_btn.grid(row=0, column=1, sticky="e")

    def _on_type(self) -> None:
        matched = self._entry_var.get().strip() == self.confirm_word
        self._action_btn.configure(state="normal" if matched else "disabled")

    def _confirm(self) -> None:
        self.destroy()
        self.on_confirm()


def show_danger_confirm(main_window, title: str, message: str, confirm_word: str,
                         action_label: str, on_confirm) -> None:
    DangerConfirmDialog(main_window, title, message, confirm_word, action_label, on_confirm)
