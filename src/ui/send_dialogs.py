"""Bulk-send pre-flight confirmation and post-send report dialogs — shared by
the WhatsApp and Email compose flows so both channels get the same
guardrails: an explicit summary + real-data preview before sending, and a
report + "Retry Failed Only" after.
"""

from __future__ import annotations

import customtkinter as ctk

from . import theme as T
from .window_utils import center_on_parent


def format_eta(total_seconds: float) -> str:
    total_seconds = max(0, int(total_seconds))
    minutes, seconds = divmod(total_seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"~{hours}h {minutes}m"
    if minutes:
        return f"~{minutes}m {seconds}s"
    return f"~{seconds}s"


class SendConfirmationDialog(ctk.CTkToplevel):
    """Pre-send summary: recipient count, channel, estimated time, a real
    rendered preview, and an explicit confirmation before anything sends."""

    def __init__(self, main_window, channel: str, recipient_count: int,
                 delay_seconds: float, preview_lines: list, on_confirm):
        super().__init__(main_window)
        self.on_confirm = on_confirm
        self.title("Confirm Send")
        center_on_parent(self, 560, 520, main_window)
        self.transient(main_window)
        self.grab_set()
        self.configure(fg_color=T.BG_MAIN)
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.bind("<Escape>", lambda _e: self.destroy())
        self.bind("<Return>", lambda _e: self._confirm())

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        ctk.CTkLabel(self, text=f"📤 Send via {channel.capitalize()}?",
                     font=ctk.CTkFont(size=18, weight="bold"), text_color=T.TEXT_HEAD).grid(
            row=0, column=0, padx=24, pady=(20, 8), sticky="w")

        stats = ctk.CTkFrame(self, fg_color=T.BG_SURFACE, corner_radius=12,
                             border_width=1, border_color=T.BG_BORDER)
        stats.grid(row=1, column=0, padx=24, pady=(0, 12), sticky="ew")
        stats.grid_columnconfigure((0, 1, 2), weight=1)
        eta = format_eta(recipient_count * delay_seconds)
        for i, (label, value) in enumerate([
            ("Recipients", str(recipient_count)),
            ("Delay between sends", f"{delay_seconds:.0f}s"),
            ("Estimated time", eta),
        ]):
            cell = ctk.CTkFrame(stats, fg_color="transparent")
            cell.grid(row=0, column=i, padx=14, pady=14, sticky="w")
            ctk.CTkLabel(cell, text=label, text_color=T.TEXT_MUTED,
                         font=ctk.CTkFont(size=11)).pack(anchor="w")
            ctk.CTkLabel(cell, text=value, text_color=T.TEXT_HEAD,
                         font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w")

        ctk.CTkLabel(self, text="Preview (real recipient data)",
                     text_color=T.TEXT_HEAD, font=ctk.CTkFont(size=12, weight="bold")).grid(
            row=2, column=0, padx=24, pady=(0, 4), sticky="nw")
        preview_box = ctk.CTkTextbox(self, fg_color=T.BG_INNER, text_color=T.TEXT_HEAD,
                                      border_color=T.BG_BORDER, border_width=1,
                                      font=ctk.CTkFont(size=12))
        preview_box.grid(row=3, column=0, padx=24, pady=(0, 12), sticky="nsew")
        preview_box.insert("1.0", "\n\n---\n\n".join(preview_lines) if preview_lines
                            else "No recipients selected.")
        preview_box.configure(state="disabled")

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=4, column=0, padx=24, pady=(0, 20), sticky="ew")
        footer.grid_columnconfigure(0, weight=1)
        ctk.CTkButton(footer, text="Cancel", width=100, fg_color=T.BADGE_BG,
                      hover_color=T.BG_BORDER, text_color=T.TEXT_HEAD,
                      command=self.destroy).grid(row=0, column=0, sticky="w")
        ctk.CTkButton(footer, text=f"Send to {recipient_count} contacts", height=38,
                      fg_color=T.ACCENT, hover_color=T.ACCENT_HOVER, text_color=T.TEXT_HEAD,
                      font=ctk.CTkFont(size=13, weight="bold"),
                      command=self._confirm).grid(row=0, column=1, sticky="e")

    def _confirm(self) -> None:
        self.destroy()
        self.on_confirm()


class SendReportDialog(ctk.CTkToplevel):
    """Post-send report: counts, delivery rate, failed-contact list with
    reasons, "Retry Failed Only", and Export (reuses the existing real
    DeliveryTracker/WhatsAppSender.export_report — not rebuilt)."""

    def __init__(self, main_window, channel: str, sent: int, failed: int,
                 failed_details: list, on_retry_failed=None, on_export=None):
        super().__init__(main_window)
        self.title("Campaign Report")
        center_on_parent(self, 520, 560, main_window)
        self.transient(main_window)
        self.grab_set()
        self.configure(fg_color=T.BG_MAIN)
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.bind("<Escape>", lambda _e: self.destroy())

        self.grid_columnconfigure(0, weight=1)
        total = sent + failed
        rate = (sent / total * 100) if total else 0

        ctk.CTkLabel(self, text="✅ Campaign complete" if failed == 0 else "⚠ Campaign complete with failures",
                     font=ctk.CTkFont(size=18, weight="bold"), text_color=T.TEXT_HEAD).grid(
            row=0, column=0, padx=24, pady=(20, 12), sticky="w")

        stats = ctk.CTkFrame(self, fg_color=T.BG_SURFACE, corner_radius=12,
                             border_width=1, border_color=T.BG_BORDER)
        stats.grid(row=1, column=0, padx=24, pady=(0, 16), sticky="ew")
        stats.grid_columnconfigure((0, 1, 2), weight=1)
        for i, (label, value, color) in enumerate([
            ("Sent", str(sent), T.SUCCESS),
            ("Failed", str(failed), T.DANGER_ON_BADGE if failed else T.TEXT_MUTED),
            ("Delivery rate", f"{rate:.0f}%", T.ACCENT),
        ]):
            cell = ctk.CTkFrame(stats, fg_color="transparent")
            cell.grid(row=0, column=i, padx=14, pady=14, sticky="w")
            ctk.CTkLabel(cell, text=label, text_color=T.TEXT_MUTED,
                         font=ctk.CTkFont(size=11)).pack(anchor="w")
            ctk.CTkLabel(cell, text=value, text_color=color,
                         font=ctk.CTkFont(size=18, weight="bold")).pack(anchor="w")

        if failed_details:
            ctk.CTkLabel(self, text=f"Failed ({len(failed_details)}) — reason shown per contact",
                         text_color=T.TEXT_HEAD, font=ctk.CTkFont(size=12, weight="bold")).grid(
                row=2, column=0, padx=24, pady=(0, 6), sticky="w")
            self.grid_rowconfigure(3, weight=1)
            fail_list = ctk.CTkScrollableFrame(self, fg_color=T.BG_INNER, corner_radius=10)
            fail_list.grid(row=3, column=0, padx=24, pady=(0, 12), sticky="nsew")
            fail_list.grid_columnconfigure(0, weight=1)
            for i, (label, reason) in enumerate(failed_details):
                row = ctk.CTkFrame(fail_list, fg_color="transparent")
                row.grid(row=i, column=0, sticky="ew", padx=8, pady=4)
                ctk.CTkLabel(row, text=label, text_color=T.TEXT_HEAD,
                             font=ctk.CTkFont(size=11, weight="bold")).pack(anchor="w")
                ctk.CTkLabel(row, text=reason, text_color=T.DANGER_ON_BADGE,
                             font=ctk.CTkFont(size=10), wraplength=440, justify="left").pack(anchor="w")

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=4, column=0, padx=24, pady=(0, 20), sticky="ew")
        if failed_details and on_retry_failed:
            ctk.CTkButton(footer, text=f"↻ Retry Failed Only ({len(failed_details)})",
                          fg_color=T.DANGER, hover_color=T.DANGER_HOVER, text_color=T.TEXT_HEAD,
                          command=lambda: (self.destroy(), on_retry_failed())).pack(side="left", padx=(0, 10))
        if on_export:
            ctk.CTkButton(footer, text="Export Report", fg_color=T.BADGE_BG,
                          hover_color=T.BG_BORDER, text_color=T.TEXT_HEAD,
                          command=on_export).pack(side="left", padx=(0, 10))
        ctk.CTkButton(footer, text="Close", fg_color=T.ACCENT, hover_color=T.ACCENT_HOVER,
                      text_color=T.TEXT_HEAD, command=self.destroy).pack(side="right")


def show_send_confirmation(main_window, channel, recipient_count, delay_seconds, preview_lines, on_confirm):
    return SendConfirmationDialog(main_window, channel, recipient_count, delay_seconds, preview_lines, on_confirm)


def show_send_report(main_window, channel, sent, failed, failed_details, on_retry_failed=None, on_export=None):
    return SendReportDialog(main_window, channel, sent, failed, failed_details, on_retry_failed, on_export)
