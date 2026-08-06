"""Bulk-send pre-flight confirmation and post-send report dialogs — shared by
the WhatsApp and Email compose flows so both channels get the same
guardrails: an explicit summary + real-data preview before sending, and a
report + "Retry Failed Only" after.
"""

from __future__ import annotations

import customtkinter as ctk

from . import theme as T
from .window_utils import center_on_parent
from ..core.send_time_advisor import recommend_send_window


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
                 delay_seconds: float, preview_lines: list, on_confirm, subject: str = "",
                 quality_flag_count: int = 0):
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

        next_row = 2

        # Item 34 (sub-item 2): a general best-practice send-time window,
        # computed purely from `channel` -- never claimed to be based on
        # this user's own send history (this app has no open/click
        # tracking), the note itself says so explicitly.
        rec = recommend_send_window(channel)
        ctk.CTkLabel(
            self, text=f"🕒 Best time to send (general guidance): {rec.window_text}",
            text_color=T.TEXT_MUTED, font=ctk.CTkFont(size=10),
            wraplength=500, justify="left").grid(
            row=next_row, column=0, padx=24, pady=(0, 6), sticky="w")
        next_row += 1

        # Item 34 (sub-item 4): a real, rule-based contact-quality flag --
        # only rendered when the caller found role-based addresses (info@,
        # noreply@, ...) among the real recipients about to be sent to.
        if quality_flag_count:
            ctk.CTkLabel(
                self,
                text=f"⚠ {quality_flag_count} recipient(s) look like role-based addresses "
                     "(info@, noreply@, support@, ...) — these often have lower "
                     "open/reply rates.",
                text_color=T.DANGER_ON_BADGE, font=ctk.CTkFont(size=10),
                wraplength=500, justify="left").grid(
                row=next_row, column=0, padx=24, pady=(0, 8), sticky="w")
            next_row += 1

        # Item 10 of the Live Testing Findings pass: an explicit subject-
        # line row for email sends (WhatsApp has no subject, so `subject`
        # is only ever passed non-empty from the email compose path).
        if subject:
            subj_row = ctk.CTkFrame(self, fg_color="transparent")
            subj_row.grid(row=next_row, column=0, padx=24, pady=(0, 12), sticky="ew")
            ctk.CTkLabel(subj_row, text="Subject", text_color=T.TEXT_MUTED,
                         font=ctk.CTkFont(size=11)).pack(anchor="w")
            ctk.CTkLabel(subj_row, text=subject, text_color=T.TEXT_HEAD,
                         font=ctk.CTkFont(size=13, weight="bold"), wraplength=500,
                         justify="left").pack(anchor="w")
            next_row += 1

        ctk.CTkLabel(self, text="Preview (real recipient data)",
                     text_color=T.TEXT_HEAD, font=ctk.CTkFont(size=12, weight="bold")).grid(
            row=next_row, column=0, padx=24, pady=(0, 4), sticky="nw")
        preview_row = next_row + 1
        self.grid_rowconfigure(preview_row, weight=1)
        preview_box = ctk.CTkTextbox(self, fg_color=T.BG_INNER, text_color=T.TEXT_HEAD,
                                      border_color=T.BG_BORDER, border_width=1,
                                      font=ctk.CTkFont(size=12))
        preview_box.grid(row=preview_row, column=0, padx=24, pady=(0, 12), sticky="nsew")
        preview_box.insert("1.0", "\n\n---\n\n".join(preview_lines) if preview_lines
                            else "No recipients selected.")
        preview_box.configure(state="disabled")

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=preview_row + 1, column=0, padx=24, pady=(0, 20), sticky="ew")
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
    """Post-send report: counts, failed-contact list with reasons, "Retry
    Failed Only", and Export (reuses the existing real
    DeliveryTracker/WhatsAppSender.export_report — not rebuilt).

    Email reports additionally show a real, honest three-state picture
    instead of assuming every SMTP-accepted send was delivered: Sent
    (attempted — SMTP accepted it), Bounced (confirmed via a real IMAP
    inbox check, only ever a positive/confirmed fact, never guessed), and
    Delivered (assumed — sent minus any confirmed bounce; email gives no
    positive delivery confirmation the way SMS/WhatsApp read-receipts can,
    so this is explicitly labeled an assumption, not a fact). `on_check_bounces`
    is only ever passed for email (WhatsApp already has its own real
    delivery-status tracking via delivery_tracker.py, a different, already-
    confirmed signal this dialog doesn't need to touch)."""

    def __init__(self, main_window, channel: str, sent: int, failed: int,
                 failed_details: list, on_retry_failed=None, on_export=None,
                 on_check_bounces=None, bounced: int = 0, on_ai_summary=None):
        super().__init__(main_window)
        self.title("Campaign Report")
        center_on_parent(self, 520, 600 if on_check_bounces else 560, main_window)
        self.transient(main_window)
        self.grab_set()
        self.configure(fg_color=T.BG_MAIN)
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.bind("<Escape>", lambda _e: self.destroy())

        self.on_check_bounces = on_check_bounces
        self.on_ai_summary = on_ai_summary
        self._sent = sent
        self._bounced = bounced
        self._bounce_checked = False

        self.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(self, text="✅ Campaign complete" if failed == 0 else "⚠ Campaign complete with failures",
                     font=ctk.CTkFont(size=18, weight="bold"), text_color=T.TEXT_HEAD).grid(
            row=0, column=0, padx=24, pady=(20, 12), sticky="w")

        stats = ctk.CTkFrame(self, fg_color=T.BG_SURFACE, corner_radius=12,
                             border_width=1, border_color=T.BG_BORDER)
        stats.grid(row=1, column=0, padx=24, pady=(0, 4 if on_check_bounces else 16), sticky="ew")
        columns = 4 if on_check_bounces else 3
        stats.grid_columnconfigure(tuple(range(columns)), weight=1)

        cells = [
            ("Sent", str(sent), T.SUCCESS),
            ("Failed", str(failed), T.DANGER_ON_BADGE if failed else T.TEXT_MUTED),
        ]
        if on_check_bounces:
            cells.append(("Bounced", str(bounced), T.DANGER_ON_BADGE if bounced else T.TEXT_MUTED))
            cells.append(("Delivered (assumed)", str(max(0, sent - bounced)), T.ACCENT))
        else:
            total = sent + failed
            rate = (sent / total * 100) if total else 0
            cells.append(("Delivery rate", f"{rate:.0f}%", T.ACCENT))

        self._bounced_value_label = None
        self._delivered_value_label = None
        for i, (label, value, color) in enumerate(cells):
            cell = ctk.CTkFrame(stats, fg_color="transparent")
            cell.grid(row=0, column=i, padx=14, pady=14, sticky="w")
            ctk.CTkLabel(cell, text=label, text_color=T.TEXT_MUTED,
                         font=ctk.CTkFont(size=11)).pack(anchor="w")
            value_label = ctk.CTkLabel(cell, text=value, text_color=color,
                                        font=ctk.CTkFont(size=18, weight="bold"))
            value_label.pack(anchor="w")
            if label == "Bounced":
                self._bounced_value_label = value_label
            elif label == "Delivered (assumed)":
                self._delivered_value_label = value_label

        next_row = 1
        if on_check_bounces:
            self._bounce_note_var = ctk.StringVar(
                value="Not checked yet — email gives no positive delivery confirmation; "
                      "\"Delivered\" above is an assumption until you check for real bounces.")
            ctk.CTkLabel(self, textvariable=self._bounce_note_var, text_color=T.TEXT_MUTED,
                         font=ctk.CTkFont(size=10), wraplength=470, justify="left").grid(
                row=next_row, column=0, padx=24, pady=(0, 12), sticky="w")
            next_row += 1

        if failed_details:
            ctk.CTkLabel(self, text=f"Failed ({len(failed_details)}) — reason shown per contact",
                         text_color=T.TEXT_HEAD, font=ctk.CTkFont(size=12, weight="bold")).grid(
                row=next_row, column=0, padx=24, pady=(0, 6), sticky="w")
            next_row += 1
            self.grid_rowconfigure(next_row, weight=1)
            fail_list = ctk.CTkScrollableFrame(self, fg_color=T.BG_INNER, corner_radius=10)
            fail_list.grid(row=next_row, column=0, padx=24, pady=(0, 12), sticky="nsew")
            fail_list.grid_columnconfigure(0, weight=1)
            for i, (label, reason) in enumerate(failed_details):
                row = ctk.CTkFrame(fail_list, fg_color="transparent")
                row.grid(row=i, column=0, sticky="ew", padx=8, pady=4)
                ctk.CTkLabel(row, text=label, text_color=T.TEXT_HEAD,
                             font=ctk.CTkFont(size=11, weight="bold")).pack(anchor="w")
                ctk.CTkLabel(row, text=reason, text_color=T.DANGER_ON_BADGE,
                             font=ctk.CTkFont(size=10), wraplength=440, justify="left").pack(anchor="w")
            next_row += 1

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=next_row, column=0, padx=24, pady=(0, 20), sticky="ew")
        if failed_details and on_retry_failed:
            ctk.CTkButton(footer, text=f"↻ Retry Failed Only ({len(failed_details)})",
                          fg_color=T.DANGER, hover_color=T.DANGER_HOVER, text_color=T.TEXT_HEAD,
                          command=lambda: (self.destroy(), on_retry_failed())).pack(side="left", padx=(0, 10))
        if on_check_bounces:
            self._check_bounces_btn = ctk.CTkButton(
                footer, text="🔍 Check for Bounces", corner_radius=6,
                fg_color=T.BG_INNER, hover_color=T.BG_BORDER,
                border_width=1, border_color=T.ACCENT, text_color=T.ACCENT_TEXT,
                font=ctk.CTkFont(size=11, weight="bold"),
                command=self._run_bounce_check)
            self._check_bounces_btn.pack(side="left", padx=(0, 10))
        if on_export:
            ctk.CTkButton(footer, text="Export Report", fg_color=T.BADGE_BG,
                          hover_color=T.BG_BORDER, text_color=T.TEXT_HEAD,
                          command=on_export).pack(side="left", padx=(0, 10))
        if on_ai_summary:
            # Item 34 (sub-item 5): a plain-language, AI-generated summary
            # of THIS real completed campaign, grounded in the real numbers
            # already shown above -- never invented data.
            self._ai_summary_btn = ctk.CTkButton(
                footer, text="🤖 AI Summary", corner_radius=6,
                fg_color=T.BG_INNER, hover_color=T.BG_BORDER,
                border_width=1, border_color=T.ACCENT, text_color=T.ACCENT_TEXT,
                font=ctk.CTkFont(size=11, weight="bold"),
                command=self._run_ai_summary)
            self._ai_summary_btn.pack(side="left", padx=(0, 10))
        ctk.CTkButton(footer, text="Close", fg_color=T.ACCENT, hover_color=T.ACCENT_HOVER,
                      text_color=T.TEXT_HEAD, command=self.destroy).pack(side="right")

    def _run_ai_summary(self) -> None:
        if not self.on_ai_summary:
            return
        self._ai_summary_btn.configure(state="disabled", text="Summarizing…")
        self.on_ai_summary(self._on_ai_summary_result)

    def _on_ai_summary_result(self, ok: bool, summary: str, error: str = "") -> None:
        if not self.winfo_exists():
            return
        self._ai_summary_btn.configure(state="normal", text="🤖 AI Summary")
        if not ok:
            from tkinter import messagebox
            messagebox.showerror("AI summary failed", error or "Unknown error.")
            return
        dlg = ctk.CTkToplevel(self)
        dlg.title("Campaign Summary")
        center_on_parent(dlg, 460, 320, self)
        dlg.resizable(False, False)
        dlg.transient(self)
        dlg.grab_set()
        dlg.configure(fg_color=T.BG_MAIN)
        dlg.bind("<Escape>", lambda _e: dlg.destroy())
        ctk.CTkLabel(dlg, text="🤖 AI Campaign Summary", font=ctk.CTkFont(size=16, weight="bold"),
                     text_color=T.TEXT_HEAD).pack(anchor="w", padx=20, pady=(20, 10))
        box = ctk.CTkTextbox(dlg, fg_color=T.BG_INNER, text_color=T.TEXT_HEAD,
                              border_color=T.BG_BORDER, border_width=1,
                              font=ctk.CTkFont(size=12), height=180)
        box.pack(fill="both", expand=True, padx=20, pady=(0, 12))
        box.insert("1.0", summary)
        box.configure(state="disabled")
        ctk.CTkButton(dlg, text="Close", fg_color=T.ACCENT, hover_color=T.ACCENT_HOVER,
                      text_color=T.TEXT_HEAD, command=dlg.destroy).pack(pady=(0, 18))

    def _run_bounce_check(self) -> None:
        if not self.on_check_bounces:
            return
        self._check_bounces_btn.configure(state="disabled", text="Checking…")
        self._bounce_note_var.set("Checking your inbox for real bounce notifications…")
        self.on_check_bounces(self._on_bounce_check_result)

    def _on_bounce_check_result(self, ok: bool, bounced_count: int, error: str = "") -> None:
        """Called back once a real bounce check finishes -- ok/bounced_count/
        error describe the CURRENT reconciled state (bounced_count is the
        real running total for this campaign, not just "new this check"),
        so re-running the check multiple times is always shown correctly."""
        if not self.winfo_exists():
            return
        self._check_bounces_btn.configure(state="normal", text="🔍 Check for Bounces")
        if not ok:
            self._bounce_note_var.set(f"⚠ Bounce check failed: {error}" if error
                                       else "⚠ Bounce check failed — see activity log for details.")
            return
        self._bounced = bounced_count
        self._bounce_checked = True
        if self._bounced_value_label is not None:
            self._bounced_value_label.configure(
                text=str(bounced_count),
                text_color=T.DANGER_ON_BADGE if bounced_count else T.TEXT_MUTED)
        if self._delivered_value_label is not None:
            self._delivered_value_label.configure(text=str(max(0, self._sent - bounced_count)))
        if bounced_count:
            self._bounce_note_var.set(
                f"✓ Checked — {bounced_count} confirmed bounce(s) found and excluded from "
                "future sends. \"Delivered\" is still an assumption for the rest — email has "
                "no positive delivery confirmation.")
        else:
            self._bounce_note_var.set(
                "✓ Checked — no bounce notifications found (yet). \"Delivered\" above is "
                "still an assumption, not a confirmed fact — some bounces can take longer "
                "to arrive; check again later if unsure.")


def show_send_confirmation(main_window, channel, recipient_count, delay_seconds, preview_lines,
                            on_confirm, subject: str = "", quality_flag_count: int = 0):
    return SendConfirmationDialog(main_window, channel, recipient_count, delay_seconds,
                                   preview_lines, on_confirm, subject=subject,
                                   quality_flag_count=quality_flag_count)


def show_send_report(main_window, channel, sent, failed, failed_details, on_retry_failed=None,
                      on_export=None, on_check_bounces=None, bounced: int = 0, on_ai_summary=None):
    return SendReportDialog(main_window, channel, sent, failed, failed_details, on_retry_failed,
                             on_export, on_check_bounces=on_check_bounces, bounced=bounced,
                             on_ai_summary=on_ai_summary)
