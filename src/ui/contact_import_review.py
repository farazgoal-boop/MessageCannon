"""Contact import review dialog — drag-and-drop or browse a file, see every
row classified (valid / invalid / duplicate) with a specific reason before
anything touches the database, choose how duplicates are handled, then
commit. Replaces the old "pick a file, get a single count" flow.
"""

from __future__ import annotations

import threading
from tkinter import filedialog, messagebox

import customtkinter as ctk

from . import theme as T
from .window_utils import center_on_parent
from ..utils.helpers import parse_dropped_file_path

try:
    from tkinterdnd2 import DND_FILES
    HAS_DND = True
except ImportError:
    HAS_DND = False

STATUS_META = {
    "invalid":     ("⚠ Invalid", T.DANGER_ON_BADGE),
    "dup_in_db":   ("⟳ Already in contacts", T.TEXT_MUTED),
    "dup_in_file":  ("⟳ Duplicate in file", T.TEXT_MUTED),
}

CHANNEL_META = {
    "both":     "✅ Ready (Email + WhatsApp)",
    "email":    "✅ Ready (Email only)",
    "whatsapp": "✅ Ready (WhatsApp only)",
}


def _status_label(row: dict) -> tuple:
    if row["status"] == "valid":
        return CHANNEL_META.get(row["channel"], "✅ Ready to import"), T.SUCCESS
    return STATUS_META.get(row["status"], ("Unknown", T.TEXT_MUTED))

SUPPORTED_FILETYPES = [
    ("Supported files", "*.csv *.xls *.xlsx *.xlsm *.html *.htm *.json *.vcf"),
    ("CSV", "*.csv"), ("Excel", "*.xls *.xlsx *.xlsm"),
    ("HTML", "*.html *.htm"), ("JSON", "*.json"), ("vCard", "*.vcf"),
]


class ContactImportReviewDialog(ctk.CTkToplevel):
    def __init__(self, main_window):
        super().__init__(main_window)
        self.main_window = main_window
        self.title("Import Contacts")
        center_on_parent(self, 760, 680, main_window)
        self.transient(main_window)
        self.grab_set()
        self.configure(fg_color=T.BG_MAIN)
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.bind("<Escape>", lambda _e: self.destroy())

        self.rows: list = []
        self.dup_resolution = ctk.StringVar(value="skip")

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.content = ctk.CTkFrame(self, fg_color="transparent")
        self.content.grid(row=0, column=0, sticky="nsew", padx=24, pady=20)
        self.content.grid_columnconfigure(0, weight=1)

        self._render_dropzone()

    # ─── Step 1: pick a file ──────────────────────────────────────────────

    def _render_dropzone(self) -> None:
        for w in self.content.winfo_children():
            w.destroy()
        self.content.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(self.content, text="📇 Import Contacts",
                     font=ctk.CTkFont(size=18, weight="bold"), text_color=T.TEXT_HEAD).grid(
            row=0, column=0, sticky="w", pady=(0, 16))

        zone = ctk.CTkFrame(self.content, fg_color=T.BG_INNER, corner_radius=14,
                            border_width=2, border_color=T.BG_BORDER)
        zone.grid(row=1, column=0, sticky="nsew")
        zone.grid_rowconfigure(0, weight=1)
        zone.grid_columnconfigure(0, weight=1)

        inner = ctk.CTkFrame(zone, fg_color="transparent")
        inner.grid(row=0, column=0)
        ctk.CTkLabel(inner, text="📂", font=ctk.CTkFont(size=48)).pack(pady=(0, 12))
        drop_text = ("Drag a CSV/Excel/HTML/JSON/vCard file here"
                     if HAS_DND else "Click Browse to pick a CSV/Excel/HTML/JSON/vCard file")
        ctk.CTkLabel(inner, text=drop_text, text_color=T.TEXT_MUTED,
                     font=ctk.CTkFont(size=13)).pack(pady=(0, 16))
        ctk.CTkButton(inner, text="Browse files…", width=180, height=38,
                      fg_color=T.ACCENT, hover_color=T.ACCENT_HOVER, text_color=T.TEXT_HEAD,
                      command=self._browse).pack()

        if HAS_DND:
            try:
                zone.drop_target_register(DND_FILES)
                zone.dnd_bind("<<Drop>>", self._on_drop)
                inner.drop_target_register(DND_FILES)
                inner.dnd_bind("<<Drop>>", self._on_drop)
            except Exception:
                pass  # DnD registration can fail on some platforms — Browse still works

    def _browse(self) -> None:
        path = filedialog.askopenfilename(title="Import Contacts", filetypes=SUPPORTED_FILETYPES)
        if path:
            self._start_analysis(path)

    def _on_drop(self, event) -> None:
        # Shared parsing now lives in utils/helpers.py -- was previously
        # duplicated, byte-for-byte, with card_creator_tab.py's own
        # _on_icon_drop, and never handled a real, documented tkinterdnd2
        # cross-platform quirk (a file:// URI instead of a plain path);
        # fixed there while investigating a live Card Creator bug report,
        # extracted here too so this sibling drop zone gets the same fix
        # instead of silently keeping the same latent gap.
        path = parse_dropped_file_path(event.data)
        if path:
            self._start_analysis(path)

    # ─── Step 2: analyze in background, then show review table ────────────

    def _render_loading(self, text: str) -> None:
        for w in self.content.winfo_children():
            w.destroy()
        self.content.grid_rowconfigure(0, weight=1)
        wrap = ctk.CTkFrame(self.content, fg_color="transparent")
        wrap.grid(row=0, column=0)
        ctk.CTkLabel(wrap, text=text, text_color=T.TEXT_MUTED,
                     font=ctk.CTkFont(size=13)).pack(pady=20)
        prog = ctk.CTkProgressBar(wrap, mode="indeterminate", width=280, progress_color=T.ACCENT)
        prog.pack()
        prog.start()

    def _start_analysis(self, path: str) -> None:
        self._source_name = path.replace("\\", "/").rsplit("/", 1)[-1]
        self._render_loading(f"Reading {path.split('/')[-1].split(chr(92))[-1]}…")

        def worker():
            try:
                analysis = self.main_window.contact_manager.analyze_import(path)
            except Exception as ex:
                # str(ex) must be computed HERE, not inside the deferred lambda:
                # Python auto-deletes an `except ... as ex` binding as soon as the
                # except block exits, which happens before self.after()'s callback
                # ever runs -- referencing `ex` inside it raises a NameError that
                # Tk's default handler swallows (prints to stderr only), silently
                # dropping the whole error report. Real bug, found while chasing
                # a live report of AI-related errors going missing app-wide.
                error_message = str(ex)
                self.after(0, lambda: self._analysis_failed(error_message))
                return
            self.after(0, lambda: self._analysis_done(analysis))

        threading.Thread(target=worker, daemon=True).start()

    def _analysis_failed(self, message: str) -> None:
        messagebox.showerror("Import failed", message, parent=self)
        self._render_dropzone()

    def _analysis_done(self, analysis: dict) -> None:
        if analysis["rows"] == [] and analysis["parse_errors"]:
            messagebox.showerror("Could not read file", "\n".join(analysis["parse_errors"]), parent=self)
            self._render_dropzone()
            return
        self.rows = analysis["rows"]
        self._render_review()

    # ─── Step 3: review table ───────────────────────────────────────────────

    def _counts(self) -> dict:
        c = {"valid": 0, "invalid": 0, "dup_in_db": 0, "dup_in_file": 0,
             "both": 0, "email": 0, "whatsapp": 0}
        for r in self.rows:
            c[r["status"]] = c.get(r["status"], 0) + 1
            if r["status"] == "valid":
                c[r["channel"]] = c.get(r["channel"], 0) + 1
        return c

    def _render_review(self) -> None:
        for w in self.content.winfo_children():
            w.destroy()
        self.content.grid_rowconfigure(2, weight=1)

        counts = self._counts()
        total_dupes = counts["dup_in_db"] + counts["dup_in_file"]

        header = ctk.CTkFrame(self.content, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(header, text=f"📇 Review {len(self.rows)} contacts",
                     font=ctk.CTkFont(size=18, weight="bold"), text_color=T.TEXT_HEAD).grid(
            row=0, column=0, sticky="w")
        ctk.CTkButton(header, text="Choose a different file", width=170, height=28,
                      fg_color=T.BADGE_BG, hover_color=T.BG_BORDER, text_color=T.TEXT_HEAD,
                      font=ctk.CTkFont(size=11), command=self._render_dropzone).grid(
            row=0, column=1, sticky="e")

        # Summary pills — channel-specific eligibility instead of one blanket
        # "Ready to import" count, so it's clear at a glance who's reachable
        # by which channel(s) rather than leaving that to per-row reading.
        pills = ctk.CTkFrame(self.content, fg_color="transparent")
        pills.grid(row=1, column=0, sticky="w", pady=(0, 10))
        for label, count, color in [
            ("Email-only", counts["email"], T.SUCCESS),
            ("WhatsApp-only", counts["whatsapp"], T.SUCCESS),
            ("Both channels", counts["both"], T.SUCCESS),
            ("Duplicates", total_dupes, T.TEXT_MUTED),
            ("Invalid", counts["invalid"], T.DANGER_ON_BADGE),
        ]:
            ctk.CTkLabel(pills, text=f"{label}: {count}", fg_color=T.BADGE_BG, corner_radius=999,
                         text_color=color, font=ctk.CTkFont(size=11, weight="bold"),
                         padx=12, pady=5).pack(side="left", padx=(0, 8))

        # Scrollable per-row table
        table = ctk.CTkScrollableFrame(self.content, fg_color=T.BG_INNER, corner_radius=12)
        table.grid(row=2, column=0, sticky="nsew", pady=(0, 12))
        table.grid_columnconfigure(0, weight=1)
        for i, row in enumerate(self.rows):
            self._build_row_widget(table, row, i)

        # Duplicate resolution + invalid note
        if total_dupes:
            dup_bar = ctk.CTkFrame(self.content, fg_color=T.BADGE_BG, corner_radius=10)
            dup_bar.grid(row=3, column=0, sticky="ew", pady=(0, 10))
            ctk.CTkLabel(dup_bar, text=f"For {total_dupes} duplicate(s) (matched by phone number):",
                         text_color=T.TEXT_HEAD, font=ctk.CTkFont(size=12, weight="bold")).pack(
                anchor="w", padx=14, pady=(10, 4))
            radios = ctk.CTkFrame(dup_bar, fg_color="transparent")
            radios.pack(anchor="w", padx=14, pady=(0, 10))
            ctk.CTkRadioButton(radios, text="Skip duplicates (keep existing data as-is)",
                               variable=self.dup_resolution, value="skip",
                               command=self._update_import_button_label,
                               text_color=T.TEXT_MUTED,
                               fg_color=T.ACCENT, border_color=T.ACCENT,
                               hover_color=T.ACCENT_HOVER).pack(anchor="w", pady=2)
            ctk.CTkRadioButton(radios, text="Merge (fill in blanks on the existing contact, never overwrites)",
                               variable=self.dup_resolution, value="merge",
                               command=self._update_import_button_label,
                               text_color=T.TEXT_MUTED,
                               fg_color=T.ACCENT, border_color=T.ACCENT,
                               hover_color=T.ACCENT_HOVER).pack(anchor="w", pady=2)

        if counts["invalid"]:
            ctk.CTkLabel(self.content, text=f"{counts['invalid']} invalid row(s) will be skipped automatically.",
                         text_color=T.TEXT_DIM, font=ctk.CTkFont(size=11)).grid(
                row=4, column=0, sticky="w", pady=(0, 8))

        # Import button — label reflects what will ACTUALLY happen for the
        # currently-selected duplicate resolution, not a static "everything" count
        btn_row = ctk.CTkFrame(self.content, fg_color="transparent")
        btn_row.grid(row=5, column=0, sticky="ew")
        btn_row.grid_columnconfigure(0, weight=1)
        self._import_btn = ctk.CTkButton(
            btn_row, text="Import", height=42,
            fg_color=T.ACCENT, hover_color=T.ACCENT_HOVER, text_color=T.TEXT_HEAD,
            font=ctk.CTkFont(size=13, weight="bold"),
            state="normal" if (counts["valid"] + total_dupes) else "disabled",
            command=self._do_commit)
        self._import_btn.grid(row=0, column=0, sticky="ew")
        self._update_import_button_label()

    def _update_import_button_label(self) -> None:
        counts = self._counts()
        total_dupes = counts["dup_in_db"] + counts["dup_in_file"]
        if self.dup_resolution.get() == "merge" and total_dupes:
            text = f"Import {counts['valid']} + merge {total_dupes}"
        else:
            text = f"Import {counts['valid']} contacts"
        self._import_btn.configure(text=text)

    def _build_row_widget(self, parent, row: dict, grid_row: int) -> None:
        status_label, status_color = _status_label(row)
        card = ctk.CTkFrame(parent, fg_color=T.BG_SURFACE, corner_radius=8)
        card.grid(row=grid_row, column=0, sticky="ew", padx=4, pady=3)
        card.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(card, text=status_label, fg_color=T.BADGE_BG, corner_radius=999,
                     text_color=status_color, font=ctk.CTkFont(size=10, weight="bold"),
                     padx=8, pady=3, width=190).grid(row=0, column=0, rowspan=2, padx=10, pady=8, sticky="w")

        name = row["name"] or "(no name)"
        contact_line = " · ".join(x for x in [row["phone"], row["email"]] if x) or "(no phone/email)"
        ctk.CTkLabel(card, text=name, text_color=T.TEXT_HEAD,
                     font=ctk.CTkFont(size=12, weight="bold"), anchor="w").grid(
            row=0, column=1, sticky="ew", padx=(0, 10), pady=(8, 0))
        ctk.CTkLabel(card, text=contact_line, text_color=T.TEXT_MUTED,
                     font=ctk.CTkFont(size=11), anchor="w").grid(
            row=1, column=1, sticky="ew", padx=(0, 10), pady=(0, 8))

        note = row.get("reason") or row.get("warning")
        if note:
            ctk.CTkLabel(card, text=note, text_color=T.DANGER_ON_BADGE if row["reason"] else T.TEXT_DIM,
                         font=ctk.CTkFont(size=10), wraplength=260, justify="right", anchor="e").grid(
                row=0, column=2, rowspan=2, padx=10, pady=8, sticky="e")

    # ─── Step 4: commit ───────────────────────────────────────────────────

    def _do_commit(self) -> None:
        self._import_btn.configure(state="disabled", text="Importing…")

        def worker():
            try:
                result = self.main_window.contact_manager.commit_import(
                    self.rows, dup_resolution=self.dup_resolution.get())
            except Exception as ex:
                error_message = str(ex)  # see _start_analysis's worker for why
                self.after(0, lambda: self._commit_failed(error_message))
                return
            self.after(0, lambda: self._render_summary(result))

        threading.Thread(target=worker, daemon=True).start()

    def _commit_failed(self, message: str) -> None:
        messagebox.showerror("Import failed", message, parent=self)
        self._import_btn.configure(state="normal", text="Import contacts")

    def _render_summary(self, result: dict) -> None:
        for w in self.content.winfo_children():
            w.destroy()
        self.main_window._record_latest_import(self.rows, self._source_name)
        self.main_window._reload_contacts()

        ctk.CTkLabel(self.content, text="✅ Import complete",
                     font=ctk.CTkFont(size=20, weight="bold"), text_color=T.TEXT_HEAD).pack(
            pady=(30, 16))

        lines = [
            (f"{result['imported']} new contacts imported", T.SUCCESS),
            (f"{result['merged']} merged into existing contacts", T.ACCENT),
            (f"{result['skipped_duplicates']} duplicates skipped", T.TEXT_MUTED),
            (f"{result['skipped_invalid']} invalid rows skipped", T.DANGER_ON_BADGE),
        ]
        for text, color in lines:
            ctk.CTkLabel(self.content, text=text, text_color=color,
                         font=ctk.CTkFont(size=13)).pack(pady=4)

        ctk.CTkButton(self.content, text="Done", width=160, height=40,
                      fg_color=T.ACCENT, hover_color=T.ACCENT_HOVER, text_color=T.TEXT_HEAD,
                      font=ctk.CTkFont(size=13, weight="bold"),
                      command=self.destroy).pack(pady=(24, 0))


def show_contact_import_review(main_window) -> ContactImportReviewDialog:
    return ContactImportReviewDialog(main_window)
