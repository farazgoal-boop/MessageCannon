"""Compose-screen "Generate with AI" dialog — user gives a short brief,
sees 2-3 genuinely different variations, picks or edits one. Shared by both
the WhatsApp and Email panels in main_window.py's Compose view.
"""

from __future__ import annotations

import threading
from tkinter import messagebox

import customtkinter as ctk

from ..core import ai_service
from ..core.ai_service import AIServiceError
from . import theme as T


class AIComposeDialog(ctk.CTkToplevel):
    def __init__(self, main_window, channel: str, on_pick):
        """channel: "whatsapp" or "email". on_pick(text, subject) is called
        with the chosen/edited variation when the user clicks "Use this"."""
        super().__init__(main_window)
        self.main_window = main_window
        self.channel = channel
        self.on_pick = on_pick

        self.title("Generate with AI")
        self.geometry("620x600")
        self.transient(main_window)
        self.grab_set()
        self.configure(fg_color=T.BG_MAIN)
        self.protocol("WM_DELETE_WINDOW", self.destroy)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.content = ctk.CTkFrame(self, fg_color="transparent")
        self.content.grid(row=0, column=0, sticky="nsew", padx=24, pady=20)
        self.content.grid_columnconfigure(0, weight=1)

        self._render_brief()

    def _render_brief(self) -> None:
        for w in self.content.winfo_children():
            w.destroy()
        self.content.grid_rowconfigure(2, weight=1)

        ctk.CTkLabel(self.content, text="✨ Generate with AI",
                     font=ctk.CTkFont(size=18, weight="bold"), text_color=T.TEXT_HEAD).grid(
            row=0, column=0, sticky="w", pady=(0, 4))
        ctk.CTkLabel(self.content,
                     text="Describe the product, tone, and goal — AI drafts a few genuinely "
                          "different options for you to pick or edit, using your real contact "
                          "variables so nothing needs re-typing.",
                     text_color=T.TEXT_MUTED, font=ctk.CTkFont(size=12),
                     wraplength=560, justify="left").grid(row=1, column=0, sticky="w", pady=(0, 14))

        self._brief_box = ctk.CTkTextbox(self.content, height=100, fg_color=T.BG_INNER,
                                          text_color=T.TEXT_HEAD, border_color=T.BG_BORDER,
                                          border_width=1, font=ctk.CTkFont(size=12))
        self._brief_box.grid(row=2, column=0, sticky="new")
        self._brief_box.insert("1.0", "e.g. Remind customers their subscription renews in 3 "
                                       "days, friendly tone, mention the {amount} due")

        self._status_var = ctk.StringVar(value="")
        ctk.CTkLabel(self.content, textvariable=self._status_var, text_color=T.DANGER_ON_BADGE,
                     font=ctk.CTkFont(size=11), wraplength=560, justify="left").grid(
            row=3, column=0, sticky="w", pady=(8, 0))

        ctk.CTkButton(self.content, text="✨ Generate", height=40, width=160,
                      fg_color=T.ACCENT, hover_color=T.ACCENT_HOVER, text_color=T.TEXT_HEAD,
                      font=ctk.CTkFont(size=13, weight="bold"),
                      command=self._generate).grid(row=4, column=0, sticky="w", pady=(14, 0))

    def _generate(self) -> None:
        api_key = self.main_window._ai_api_key.get()
        if not api_key:
            messagebox.showwarning(
                "No API key", "Add your Anthropic API key in Settings → AI Cards first.",
                parent=self)
            return
        brief = self._brief_box.get("1.0", "end").strip()
        if not brief:
            self._status_var.set("Describe what you want to say first.")
            return

        sample_vars = self._sample_variables()
        self._render_loading()

        def worker():
            try:
                variations = ai_service.generate_message_variations(
                    brief, self.channel, api_key, count=3, sample_variables=sample_vars)
            except AIServiceError as ex:
                self.after(0, lambda: self._generation_failed(str(ex)))
                return
            self.after(0, lambda: self._render_variations(variations))

        threading.Thread(target=worker, daemon=True).start()

    def _sample_variables(self):
        contacts = self.main_window._get_selected_contacts()
        names = {"name"}
        if contacts:
            names.update(contacts[0].custom_fields.keys())
        return sorted(names)

    def _render_loading(self) -> None:
        for w in self.content.winfo_children():
            w.destroy()
        self.content.grid_rowconfigure(0, weight=1)
        wrap = ctk.CTkFrame(self.content, fg_color="transparent")
        wrap.grid(row=0, column=0)
        ctk.CTkLabel(wrap, text="Generating variations…", text_color=T.TEXT_MUTED,
                     font=ctk.CTkFont(size=13)).pack(pady=20)
        prog = ctk.CTkProgressBar(wrap, mode="indeterminate", width=280, progress_color=T.ACCENT)
        prog.pack()
        prog.start()

    def _generation_failed(self, message: str) -> None:
        self._render_brief()
        self._status_var.set(f"⚠ {message}")

    def _render_variations(self, variations) -> None:
        for w in self.content.winfo_children():
            w.destroy()
        self.content.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(self.content, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(header, text=f"Pick one of {len(variations)} variations",
                     font=ctk.CTkFont(size=16, weight="bold"), text_color=T.TEXT_HEAD).grid(
            row=0, column=0, sticky="w")
        ctk.CTkButton(header, text="↻ Try again", width=110, height=28,
                      fg_color=T.BADGE_BG, hover_color=T.BG_BORDER, text_color=T.TEXT_HEAD,
                      font=ctk.CTkFont(size=11), command=self._render_brief).grid(
            row=0, column=1, sticky="e")

        scroll = ctk.CTkScrollableFrame(self.content, fg_color="transparent")
        scroll.grid(row=1, column=0, sticky="nsew")
        scroll.grid_columnconfigure(0, weight=1)

        for i, variation in enumerate(variations):
            self._build_variation_card(scroll, variation, i)

    def _build_variation_card(self, parent, variation: dict, index: int) -> None:
        card = ctk.CTkFrame(parent, fg_color=T.BG_SURFACE, corner_radius=12,
                            border_width=1, border_color=T.BG_BORDER)
        card.grid(row=index, column=0, sticky="ew", pady=(0, 12))
        card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(card, text=variation.get("label") or f"Variation {index + 1}",
                     fg_color=T.BADGE_BG, corner_radius=999, text_color=T.ACCENT,
                     font=ctk.CTkFont(size=11, weight="bold"), padx=10, pady=4).grid(
            row=0, column=0, padx=14, pady=(14, 8), sticky="w")

        subject_var = ctk.StringVar(value=variation.get("subject", ""))
        if self.channel == "email":
            ctk.CTkLabel(card, text="Subject", text_color=T.TEXT_MUTED,
                         font=ctk.CTkFont(size=11)).grid(row=1, column=0, padx=14, sticky="w")
            subj_entry = ctk.CTkEntry(card, textvariable=subject_var, fg_color=T.BG_INNER,
                                       border_color=T.BG_BORDER, text_color=T.TEXT_HEAD,
                                       placeholder_text="Subject (editable)")
            subj_entry.grid(row=2, column=0, padx=14, pady=(2, 8), sticky="ew")

        text_box = ctk.CTkTextbox(card, height=90, fg_color=T.BG_INNER, text_color=T.TEXT_HEAD,
                                   border_color=T.BG_BORDER, border_width=1,
                                   font=ctk.CTkFont(size=12))
        text_box.grid(row=3, column=0, padx=14, pady=(0, 10), sticky="ew")
        text_box.insert("1.0", variation.get("text", ""))

        def use_this():
            self.on_pick(text_box.get("1.0", "end").strip(), subject_var.get().strip())
            self.destroy()

        ctk.CTkButton(card, text="Use this ✓", width=140, height=32,
                      fg_color=T.ACCENT, hover_color=T.ACCENT_HOVER, text_color=T.TEXT_HEAD,
                      font=ctk.CTkFont(size=12, weight="bold"), command=use_this).grid(
            row=4, column=0, padx=14, pady=(0, 14), sticky="w")


def show_ai_compose_dialog(main_window, channel: str, on_pick) -> AIComposeDialog:
    return AIComposeDialog(main_window, channel, on_pick)
