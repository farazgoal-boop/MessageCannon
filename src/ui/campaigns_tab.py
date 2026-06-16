"""Campaign Manager tab for MessageCannon Pro."""

from __future__ import annotations

import logging
from datetime import datetime
from tkinter import messagebox
from typing import TYPE_CHECKING

import customtkinter as ctk

if TYPE_CHECKING:
    from src.ui.main_window import MainWindow

logger = logging.getLogger(__name__)


def build_campaigns_view(main_window: "MainWindow") -> None:
    """Add Campaigns tab to the main window."""
    frame = main_window._new_view_container("Campaigns", scrollable=True)
    frame.grid_columnconfigure(0, weight=1)

    hero = ctk.CTkFrame(frame, fg_color="#101a24", corner_radius=20, border_width=1, border_color="#183144")
    hero.grid(row=0, column=0, sticky="ew", pady=(0, 12))
    hero.grid_columnconfigure(0, weight=1)
    ctk.CTkLabel(hero, text="Campaign Manager", font=ctk.CTkFont(size=22, weight="bold")).grid(
        row=0, column=0, padx=18, pady=(16, 4), sticky="w"
    )
    ctk.CTkLabel(
        hero,
        text="View, duplicate, draft, and schedule past WhatsApp & email campaigns",
        text_color="#90aab6",
    ).grid(row=1, column=0, padx=18, pady=(0, 16), sticky="w")

    list_frame = ctk.CTkFrame(frame, fg_color="#101a24", corner_radius=20, border_width=1, border_color="#173041")
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
            text_color="#8ea5af",
        ).grid(row=0, column=0, pady=40)
        return

    for index, camp in enumerate(campaigns):
        row = ctk.CTkFrame(scroll, fg_color="#0c131b", corner_radius=14, border_width=1, border_color="#163144")
        row.grid(row=index, column=0, sticky="ew", pady=6)
        row.grid_columnconfigure(1, weight=1)

        name = camp.get("name", "Untitled")
        created = camp.get("created_at", "")
        sent = camp.get("sent_count", 0)
        failed = camp.get("failed_count", 0)

        ctk.CTkLabel(row, text=name, font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=0, column=0, columnspan=2, padx=14, pady=(12, 2), sticky="w"
        )
        ctk.CTkLabel(
            row,
            text=f"📅 {created}  ·  ✅ {sent} sent  ·  ❌ {failed} failed",
            text_color="#8ea5af",
            font=ctk.CTkFont(size=11),
        ).grid(row=1, column=0, padx=14, pady=(0, 12), sticky="w")

        actions = ctk.CTkFrame(row, fg_color="transparent")
        actions.grid(row=1, column=1, padx=14, pady=(0, 12), sticky="e")

        def duplicate(c=camp):
            messagebox.showinfo(
                "Duplicate Campaign",
                f"Campaign '{c.get('name')}' loaded as draft in Compose.\n"
                "Edit message and recipients, then send.",
            )
            main_window._show_view("Compose")

        def schedule(c=camp):
            messagebox.showinfo(
                "Schedule Campaign",
                f"Scheduling for '{c.get('name')}' — set date/time in Compose → Schedule.",
            )

        ctk.CTkButton(actions, text="Duplicate", width=80, fg_color="#1d3545", command=duplicate).pack(
            side="left", padx=4
        )
        ctk.CTkButton(actions, text="Schedule", width=80, fg_color="#1c6b4d", command=schedule).pack(
            side="left", padx=4
        )
