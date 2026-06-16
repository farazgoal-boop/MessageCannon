"""
MessageCannon Pro - Email Tab (tkinter)
Drop-in tab to add to existing notebook in main.py
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import threading
import json
import os
from pathlib import Path

# ── Import our new modules ────────────────────────────────────────────────────
from modules.email_sender import (
    BulkEmailSender, SMTPConfig, EmailCampaign,
    SMTP_PRESETS, get_template_names, get_template
)
from modules.data_importer import UniversalDataImporter


class EmailTab(ttk.Frame):
    """
    Complete Email Campaign tab.
    Usage in main.py:
        from ui.email_tab import EmailTab
        email_tab = EmailTab(notebook, theme_vars)
        notebook.add(email_tab, text="📧 Email")
    """

    def __init__(self, parent, theme_vars=None):
        super().__init__(parent)
        self.theme_vars = theme_vars or {}
        self.sender     = BulkEmailSender()
        self.importer   = UniversalDataImporter()
        self.contacts   = []
        self.is_sending = False

        self._build_ui()

    # ─── UI Build ─────────────────────────────────────────────────────────────

    def _build_ui(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        paned = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        paned.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)

        # Left: Config + Contacts
        left = ttk.Frame(paned, width=340)
        paned.add(left, weight=1)
        self._build_left(left)

        # Right: Compose + Send
        right = ttk.Frame(paned)
        paned.add(right, weight=2)
        self._build_right(right)

    def _build_left(self, parent):
        parent.columnconfigure(0, weight=1)

        # ── SMTP Config ──────────────────────────────────────────────────────
        smtp_frame = ttk.LabelFrame(parent, text="📮 SMTP Settings", padding=10)
        smtp_frame.grid(row=0, column=0, sticky="ew", padx=4, pady=4)
        smtp_frame.columnconfigure(1, weight=1)

        # Provider preset
        ttk.Label(smtp_frame, text="Provider:").grid(row=0, column=0, sticky="w", pady=2)
        self.preset_var = tk.StringVar(value="Gmail")
        preset_cb = ttk.Combobox(smtp_frame, textvariable=self.preset_var,
                                  values=list(SMTP_PRESETS.keys()), state="readonly")
        preset_cb.grid(row=0, column=1, sticky="ew", pady=2, padx=(4,0))
        preset_cb.bind("<<ComboboxSelected>>", self._on_preset_change)

        # SMTP host / port
        ttk.Label(smtp_frame, text="Host:").grid(row=1, column=0, sticky="w", pady=2)
        self.smtp_host = tk.StringVar(value="smtp.gmail.com")
        ttk.Entry(smtp_frame, textvariable=self.smtp_host).grid(
            row=1, column=1, sticky="ew", pady=2, padx=(4,0))

        ttk.Label(smtp_frame, text="Port:").grid(row=2, column=0, sticky="w", pady=2)
        self.smtp_port = tk.StringVar(value="587")
        ttk.Entry(smtp_frame, textvariable=self.smtp_port, width=8).grid(
            row=2, column=1, sticky="w", pady=2, padx=(4,0))

        ttk.Label(smtp_frame, text="Username:").grid(row=3, column=0, sticky="w", pady=2)
        self.smtp_user = tk.StringVar()
        ttk.Entry(smtp_frame, textvariable=self.smtp_user).grid(
            row=3, column=1, sticky="ew", pady=2, padx=(4,0))

        ttk.Label(smtp_frame, text="Password:").grid(row=4, column=0, sticky="w", pady=2)
        self.smtp_pass = tk.StringVar()
        ttk.Entry(smtp_frame, textvariable=self.smtp_pass, show="●").grid(
            row=4, column=1, sticky="ew", pady=2, padx=(4,0))

        ttk.Label(smtp_frame, text="Sender Name:").grid(row=5, column=0, sticky="w", pady=2)
        self.sender_name = tk.StringVar(value="My Business")
        ttk.Entry(smtp_frame, textvariable=self.sender_name).grid(
            row=5, column=1, sticky="ew", pady=2, padx=(4,0))

        ttk.Label(smtp_frame, text="Sender Email:").grid(row=6, column=0, sticky="w", pady=2)
        self.sender_email = tk.StringVar()
        ttk.Entry(smtp_frame, textvariable=self.sender_email).grid(
            row=6, column=1, sticky="ew", pady=2, padx=(4,0))

        ttk.Label(smtp_frame, text="Delay (sec):").grid(row=7, column=0, sticky="w", pady=2)
        self.delay_var = tk.StringVar(value="5")
        ttk.Entry(smtp_frame, textvariable=self.delay_var, width=8).grid(
            row=7, column=1, sticky="w", pady=2, padx=(4,0))

        ttk.Button(smtp_frame, text="🔌 Test Connection",
                   command=self._test_connection).grid(
            row=8, column=0, columnspan=2, sticky="ew", pady=(8,0))

        # ── Contacts ─────────────────────────────────────────────────────────
        contact_frame = ttk.LabelFrame(parent, text="👥 Contacts", padding=10)
        contact_frame.grid(row=1, column=0, sticky="nsew", padx=4, pady=4)
        contact_frame.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)

        ttk.Button(contact_frame, text="📂 Import CSV / Excel / HTML",
                   command=self._import_contacts).grid(
            row=0, column=0, columnspan=2, sticky="ew", pady=(0,4))

        self.contact_count_label = ttk.Label(contact_frame, text="No contacts loaded")
        self.contact_count_label.grid(row=1, column=0, columnspan=2, sticky="w")

        # Mini list
        self.contact_list = tk.Listbox(contact_frame, height=8, font=("Courier", 9))
        sb = ttk.Scrollbar(contact_frame, command=self.contact_list.yview)
        self.contact_list.configure(yscrollcommand=sb.set)
        self.contact_list.grid(row=2, column=0, sticky="nsew", pady=(4,0))
        sb.grid(row=2, column=1, sticky="ns", pady=(4,0))
        contact_frame.rowconfigure(2, weight=1)

    def _build_right(self, parent):
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)

        # ── Campaign ─────────────────────────────────────────────────────────
        top = ttk.LabelFrame(parent, text="✉️ Campaign", padding=10)
        top.grid(row=0, column=0, sticky="ew", padx=4, pady=4)
        top.columnconfigure(1, weight=1)

        ttk.Label(top, text="Template:").grid(row=0, column=0, sticky="w")
        self.template_var = tk.StringVar(value="(none)")
        tpl_cb = ttk.Combobox(top, textvariable=self.template_var,
                               values=["(none)"] + get_template_names(),
                               state="readonly")
        tpl_cb.grid(row=0, column=1, sticky="ew", padx=(4,0))
        tpl_cb.bind("<<ComboboxSelected>>", self._on_template_select)

        ttk.Label(top, text="Subject:").grid(row=1, column=0, sticky="w", pady=(6,0))
        self.subject_var = tk.StringVar(value="Hello {name}, we have news for you!")
        ttk.Entry(top, textvariable=self.subject_var).grid(
            row=1, column=1, sticky="ew", padx=(4,0), pady=(6,0))

        ttk.Label(top, text="Reply-To:").grid(row=2, column=0, sticky="w", pady=2)
        self.reply_to_var = tk.StringVar()
        ttk.Entry(top, textvariable=self.reply_to_var).grid(
            row=2, column=1, sticky="ew", padx=(4,0), pady=2)

        # Attachments
        ttk.Label(top, text="Attachments:").grid(row=3, column=0, sticky="w")
        attach_row = ttk.Frame(top)
        attach_row.grid(row=3, column=1, sticky="ew", padx=(4,0))
        self.attach_label = ttk.Label(attach_row, text="None", foreground="gray")
        self.attach_label.pack(side="left")
        ttk.Button(attach_row, text="Browse", width=8,
                   command=self._add_attachment).pack(side="right")
        self._attachments = []

        # ── HTML Body ────────────────────────────────────────────────────────
        body_frame = ttk.LabelFrame(parent, text="📝 HTML Body (supports {name}, {email}, etc.)",
                                    padding=10)
        body_frame.grid(row=1, column=0, sticky="nsew", padx=4, pady=4)
        body_frame.columnconfigure(0, weight=1)
        body_frame.rowconfigure(0, weight=1)

        self.body_editor = scrolledtext.ScrolledText(
            body_frame, wrap=tk.WORD, font=("Courier New", 10), height=14)
        self.body_editor.grid(row=0, column=0, sticky="nsew")
        self.body_editor.insert("1.0", "<p>Dear <strong>{name}</strong>,</p>\n<p>Your message here.</p>")

        # ── Progress + Controls ───────────────────────────────────────────────
        bottom = ttk.Frame(parent)
        bottom.grid(row=2, column=0, sticky="ew", padx=4, pady=4)
        bottom.columnconfigure(1, weight=1)

        self.progress_bar = ttk.Progressbar(bottom, mode="determinate")
        self.progress_bar.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0,6))

        self.status_label = ttk.Label(bottom, text="Ready.", foreground="gray")
        self.status_label.grid(row=1, column=0, columnspan=2, sticky="w")

        self.start_btn = ttk.Button(bottom, text="🚀 Start Email Campaign",
                                    command=self._start_sending)
        self.start_btn.grid(row=2, column=0, sticky="ew", padx=(0,4), pady=(4,0))

        self.stop_btn = ttk.Button(bottom, text="⏹ Stop", command=self._stop_sending,
                                   state="disabled")
        self.stop_btn.grid(row=2, column=1, sticky="ew", pady=(4,0))

        self.log_box = scrolledtext.ScrolledText(bottom, height=5, state="disabled",
                                                  font=("Courier New", 9))
        self.log_box.grid(row=3, column=0, columnspan=3, sticky="ew", pady=(8,0))

    # ─── Event Handlers ───────────────────────────────────────────────────────

    def _on_preset_change(self, _=None):
        preset = SMTP_PRESETS.get(self.preset_var.get(), {})
        if preset.get("host"):
            self.smtp_host.set(preset["host"])
            self.smtp_port.set(str(preset["port"]))

    def _on_template_select(self, _=None):
        name = self.template_var.get()
        tpl = get_template(name)
        if tpl:
            self.subject_var.set(tpl.get("subject", ""))
            self.body_editor.delete("1.0", tk.END)
            self.body_editor.insert("1.0", tpl.get("html", ""))

    def _add_attachment(self):
        paths = filedialog.askopenfilenames(title="Select attachments")
        if paths:
            self._attachments = list(paths)
            names = ", ".join(Path(p).name for p in paths)
            self.attach_label.config(text=names, foreground="black")

    def _import_contacts(self):
        path = filedialog.askopenfilename(
            title="Import Contacts",
            filetypes=[
                ("All supported", "*.csv *.xls *.xlsx *.xlsm *.html *.htm"),
                ("CSV files", "*.csv"),
                ("Excel files", "*.xls *.xlsx *.xlsm"),
                ("HTML files", "*.html *.htm"),
            ]
        )
        if not path:
            return

        result = self.importer.import_file(path)
        self.contacts = result.contacts

        self.contact_list.delete(0, tk.END)
        for c in self.contacts:
            label = f"{c.get('name','?'):20} {c.get('email','(no email)'):30}"
            self.contact_list.insert(tk.END, label)

        if result.errors:
            messagebox.showwarning("Import Warnings",
                                   "\n".join(result.errors[:5]))

        self.contact_count_label.config(
            text=f"✅ {result.total} contacts loaded  |  ⚠️ {result.skipped} skipped")
        self._log(result.summary())

    def _test_connection(self):
        config = self._build_config()
        ok, msg = self.sender.test_connection(config)
        if ok:
            messagebox.showinfo("Connection Test", msg)
        else:
            messagebox.showerror("Connection Failed", msg)

    def _build_config(self) -> SMTPConfig:
        return SMTPConfig(
            host=self.smtp_host.get().strip(),
            port=int(self.smtp_port.get() or 587),
            username=self.smtp_user.get().strip(),
            password=self.smtp_pass.get(),
            sender_name=self.sender_name.get().strip(),
            sender_email=self.sender_email.get().strip(),
            use_tls=True,
        )

    def _build_campaign(self) -> EmailCampaign:
        return EmailCampaign(
            name="Campaign",
            subject=self.subject_var.get(),
            body_html=self.body_editor.get("1.0", tk.END),
            reply_to=self.reply_to_var.get().strip(),
            attachments=self._attachments,
            delay_seconds=float(self.delay_var.get() or 5),
        )

    def _start_sending(self):
        if not self.contacts:
            messagebox.showwarning("No Contacts", "Please import contacts first.")
            return

        email_contacts = [c for c in self.contacts if c.get("email")]
        if not email_contacts:
            messagebox.showerror("No Emails",
                                 "None of your contacts have an email address.")
            return

        if not messagebox.askyesno("Confirm Send",
                f"Send to {len(email_contacts)} contacts?\n\n"
                "Make sure you have consent from all recipients."):
            return

        config   = self._build_config()
        campaign = self._build_campaign()

        self.progress_bar["maximum"] = len(email_contacts)
        self.progress_bar["value"]   = 0
        self.is_sending = True
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self._log(f"Starting campaign → {len(email_contacts)} recipients")

        self.sender.send_campaign(
            config, campaign, email_contacts,
            on_progress=self._on_progress,
            on_done=self._on_done,
        )

    def _stop_sending(self):
        self.sender.stop()
        self._log("⏹ Stop requested…")

    def _on_progress(self, sent, failed, total, current):
        self.after(0, self._update_progress, sent, failed, total, current)

    def _update_progress(self, sent, failed, total, current):
        self.progress_bar["value"] = sent + failed
        self.status_label.config(
            text=f"Sent: {sent}  Failed: {failed}  Total: {total}  → {current}")
        self._log(f"✅ Sent → {current}")

    def _on_done(self, result):
        self.after(0, self._finish, result)

    def _finish(self, result):
        self.is_sending = False
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        msg = (f"Campaign complete!\n\n"
               f"✅ Sent:   {result.sent}\n"
               f"❌ Failed: {result.failed}\n"
               f"⚠️ Skipped: {result.skipped}")
        if result.stopped_early:
            msg += "\n\n(Stopped early)"
        messagebox.showinfo("Done", msg)
        self._log(f"Campaign done. Sent={result.sent} Failed={result.failed}")

    def _log(self, text: str):
        self.log_box.config(state="normal")
        self.log_box.insert(tk.END, text + "\n")
        self.log_box.see(tk.END)
        self.log_box.config(state="disabled")
