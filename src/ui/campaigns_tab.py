"""Campaign Manager tab for MessageCannon Pro."""

from __future__ import annotations

import logging
from datetime import datetime
from tkinter import messagebox
from typing import TYPE_CHECKING

import customtkinter as ctk
from . import theme as T

if TYPE_CHECKING:
    from src.ui.main_window import MainWindow

logger = logging.getLogger(__name__)


def build_campaigns_view(main_window: "MainWindow") -> None:
    """Add Campaigns tab to the main window."""
    frame = main_window._new_view_container("Campaigns", scrollable=True)
    frame.grid_columnconfigure(0, weight=1)

    hero = ctk.CTkFrame(frame, fg_color=T.BG_SURFACE, corner_radius=14,
                        border_width=1, border_color=T.BG_BORDER)
    hero.grid(row=0, column=0, sticky="ew", pady=(0, 10))
    hero.grid_columnconfigure(0, weight=1)
    ctk.CTkLabel(hero, text="Campaign Manager",
                 font=ctk.CTkFont(size=15, weight="bold"),
                 text_color=T.TEXT_HEAD).grid(
        row=0, column=0, padx=18, pady=(14, 4), sticky="w")
    ctk.CTkLabel(
        hero,
        text="View and duplicate past email campaigns — opens them ready to send in Compose.",
        text_color=T.TEXT_MUTED,
        font=ctk.CTkFont(size=12),
    ).grid(row=1, column=0, padx=18, pady=(0, 14), sticky="w")

    list_frame = ctk.CTkFrame(frame, fg_color=T.BG_SURFACE, corner_radius=14,
                              border_width=1, border_color=T.BG_BORDER)
    list_frame.grid(row=1, column=0, sticky="nsew")
    list_frame.grid_columnconfigure(0, weight=1)
    frame.grid_rowconfigure(1, weight=1)

    scroll = ctk.CTkScrollableFrame(list_frame, fg_color="transparent")
    scroll.grid(row=0, column=0, sticky="nsew", padx=12, pady=12)
    scroll.grid_columnconfigure(0, weight=1)
    list_frame.grid_rowconfigure(0, weight=1)

    campaigns = main_window.db.get_recent_campaigns_summary(limit=50)
    if not campaigns:
        ctk.CTkLabel(
            scroll,
            text="No campaigns yet. Start a WhatsApp or Email campaign to see history here.",
            text_color=T.TEXT_MUTED,
            font=ctk.CTkFont(size=13),
        ).grid(row=0, column=0, pady=40)
        return

    for index, camp in enumerate(campaigns):
        row = ctk.CTkFrame(scroll, fg_color=T.BG_INNER, corner_radius=10,
                           border_width=1, border_color=T.BG_BORDER)
        row.grid(row=index, column=0, sticky="ew", pady=4)
        row.grid_columnconfigure(1, weight=1)

        name = camp.get("name", "Untitled")
        created = camp.get("created_at", "")
        sent = camp.get("sent_count", 0)
        failed = camp.get("failed_count", 0)

        ctk.CTkLabel(row, text=name,
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=T.TEXT_HEAD).grid(
            row=0, column=0, columnspan=2, padx=14, pady=(10, 2), sticky="w")
        ctk.CTkLabel(
            row,
            text=f"📅 {created}  ·  ✅ {sent} sent  ·  ❌ {failed} failed",
            text_color=T.TEXT_MUTED,
            font=ctk.CTkFont(size=11),
        ).grid(row=1, column=0, padx=14, pady=(0, 10), sticky="w")

        actions = ctk.CTkFrame(row, fg_color="transparent")
        actions.grid(row=1, column=1, padx=14, pady=(0, 10), sticky="e")

        def duplicate(c=camp):
            main_window._em_subj_var.set(c.get("message_template", ""))
            main_window._compose_channel_var.set("Email")
            main_window._on_channel_switch("Email")
            main_window._show_view("Compose")

        ctk.CTkButton(actions, text="Duplicate", width=80,
                      corner_radius=6,
                      fg_color=T.BADGE_BG, hover_color=T.BG_BORDER,
                      text_color=T.TEXT_HEAD,
                      command=duplicate).pack(side="left", padx=4)
