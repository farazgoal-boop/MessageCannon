"""First-run setup wizard — Welcome, channel choice, then per-channel
credentials/connect, a real test, and a real test send. State persists via
MainWindow._save_wizard_progress so closing mid-wizard resumes correctly.
"""

from __future__ import annotations

import threading
from tkinter import messagebox

import customtkinter as ctk

from ..models import Contact
from ..utils.validators import DataValidator, PhoneValidator
from . import theme as T

SMTP_PRESETS = {
    "Gmail":   ("smtp.gmail.com", "587"),
    "Outlook": ("smtp-mail.outlook.com", "587"),
    "Yahoo":   ("smtp.mail.yahoo.com", "587"),
    "Custom":  ("", "587"),
}


class SetupWizard(ctk.CTkToplevel):
    # Real bug found via live user testing (not caught by any prior driver-
    # based verification): a fixed 620x660, non-resizable, non-scrolling
    # window meant the email_creds step's ~30 stacked widgets could exceed
    # the pack cavity on a real user's screen/DPI scaling -- the footer
    # (Continue/Test buttons) then got squeezed out and unmapped entirely,
    # so neither the mouse nor Tab traversal could ever reach it. Fixed by
    # separating a pinned, always-visible footer from a genuinely scrollable
    # content area, plus a resizable window with a sane minsize as a second
    # safety net.
    DEFAULT_WIDTH = 640
    DEFAULT_HEIGHT = 720
    MIN_WIDTH = 480
    MIN_HEIGHT = 420

    def __init__(self, main_window, force_restart: bool = False):
        super().__init__(main_window)
        self.main_window = main_window
        self.title("MessageCannon Pro — Setup")
        self._size_and_center()
        self.resizable(True, True)
        self.minsize(self.MIN_WIDTH, self.MIN_HEIGHT)
        self.transient(main_window)
        self.grab_set()
        self.configure(fg_color=T.BG_MAIN)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.bind("<Escape>", lambda _e: self._on_close())

        resumable = main_window.setup_wizard_channels or main_window.setup_wizard_substep
        if force_restart or not resumable:
            self.channels = []
            self.channel_index = 0
            self.substep = "welcome"
        else:
            self.channels = list(main_window.setup_wizard_channels)
            self.channel_index = main_window.setup_wizard_channel_index
            self.substep = main_window.setup_wizard_substep or "welcome"

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)  # scrollable step content
        self.grid_rowconfigure(1, weight=0)  # pinned footer -- never scrolls away

        # The actual step content (headings, fields, status pills) goes in
        # here -- a real CTkScrollableFrame, so it can never silently exceed
        # the window and hide anything below it.
        self.content = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.content.grid(row=0, column=0, sticky="nsew", padx=32, pady=(20, 0))

        # Continue/Back/Test buttons live here instead, outside the scroll
        # region, so they are always visible and reachable regardless of how
        # tall a given step's content is.
        self.footer = ctk.CTkFrame(self, fg_color="transparent")
        self.footer.grid(row=1, column=0, sticky="ew", padx=32, pady=(8, 20))

        self._render()

    def _size_and_center(self) -> None:
        """Open at a size that's guaranteed to fit the real screen, and
        centered on it -- rather than a fixed geometry string that assumes
        a screen/DPI scale this app has no control over."""
        self.update_idletasks()
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        width = min(self.DEFAULT_WIDTH, max(self.MIN_WIDTH, screen_w - 80))
        height = min(self.DEFAULT_HEIGHT, max(self.MIN_HEIGHT, screen_h - 80))
        x = max(0, (screen_w - width) // 2)
        y = max(0, (screen_h - height) // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")

    # ─── Navigation ───────────────────────────────────────────────────────

    def _on_close(self) -> None:
        self.destroy()

    def _goto(self, substep: str) -> None:
        self.substep = substep
        self.main_window._save_wizard_progress(
            setup_wizard_channels=self.channels,
            setup_wizard_channel_index=self.channel_index,
            setup_wizard_substep=substep,
        )
        self._render()

    def _start_channel(self, channel: str) -> None:
        self._goto("email_creds" if channel == "email" else "whatsapp_connect")

    def _advance_after_channel_done(self) -> None:
        self.channel_index += 1
        if self.channel_index < len(self.channels):
            self._start_channel(self.channels[self.channel_index])
        else:
            self._goto("done")

    def _skip(self) -> None:
        self.main_window._save_wizard_progress(setup_wizard_skipped=True)
        self.main_window._refresh_setup_banner()
        self.destroy()

    def _render(self) -> None:
        for w in self.content.winfo_children():
            w.destroy()
        for w in self.footer.winfo_children():
            w.destroy()
        renderers = {
            "welcome": self._render_welcome,
            "channel_choice": self._render_channel_choice,
            "email_creds": self._render_email_creds,
            "email_test": self._render_email_test,
            "email_send": self._render_email_send,
            "whatsapp_connect": self._render_whatsapp_connect,
            "whatsapp_send": self._render_whatsapp_send,
            "done": self._render_done,
        }
        renderers.get(self.substep, self._render_welcome)()

    def _footer(self, next_cmd, back_cmd=None, next_label="Continue"):
        # Pinned in self.footer -- a sibling of the scrollable self.content,
        # never inside it -- so Continue/Back are always visible and never
        # get pushed out of the pack cavity by tall step content.
        row = self.footer
        if back_cmd:
            ctk.CTkButton(row, text="← Back", width=90, fg_color=T.BADGE_BG,
                          hover_color=T.BG_BORDER, text_color=T.TEXT_HEAD,
                          command=back_cmd).pack(side="left")
        btn = ctk.CTkButton(row, text=next_label, width=140, height=38,
                             fg_color=T.ACCENT, hover_color=T.ACCENT_HOVER,
                             text_color=T.TEXT_HEAD, font=ctk.CTkFont(size=13, weight="bold"),
                             command=next_cmd)
        btn.pack(side="right")
        return btn

    # ─── Steps ────────────────────────────────────────────────────────────

    def _render_welcome(self) -> None:
        c = self.content
        ctk.CTkLabel(c, text="👋 Welcome to MessageCannon Pro",
                     font=ctk.CTkFont(size=22, weight="bold"), text_color=T.TEXT_HEAD).pack(pady=(30, 8))
        ctk.CTkLabel(c, text="Let's get your first campaign channel connected — about 3 minutes.",
                     text_color=T.TEXT_MUTED, font=ctk.CTkFont(size=13)).pack(pady=(0, 30))

        def pick(channel: str) -> None:
            self.channels = [channel]
            self.channel_index = 0
            self._goto("channel_choice")

        btn_frame = ctk.CTkFrame(c, fg_color="transparent")
        btn_frame.pack(pady=10)
        ctk.CTkButton(btn_frame, text="📧  Connect Email", width=240, height=44,
                      fg_color=T.ACCENT, hover_color=T.ACCENT_HOVER, text_color=T.TEXT_HEAD,
                      font=ctk.CTkFont(size=13, weight="bold"),
                      command=lambda: pick("email")).pack(pady=6)
        ctk.CTkButton(btn_frame, text="📱  Connect WhatsApp", width=240, height=44,
                      fg_color=T.ACCENT, hover_color=T.ACCENT_HOVER, text_color=T.TEXT_HEAD,
                      font=ctk.CTkFont(size=13, weight="bold"),
                      command=lambda: pick("whatsapp")).pack(pady=6)
        ctk.CTkButton(btn_frame, text="Skip for now", width=240, height=32,
                      fg_color="transparent", hover_color=T.BG_INNER, text_color=T.TEXT_MUTED,
                      command=self._skip).pack(pady=(16, 0))

    def _render_channel_choice(self) -> None:
        c = self.content
        ctk.CTkLabel(c, text="Which channel(s) do you want to set up?",
                     font=ctk.CTkFont(size=17, weight="bold"), text_color=T.TEXT_HEAD).pack(
            anchor="w", pady=(20, 16))

        default = "both" if len(self.channels) > 1 else (self.channels[0] if self.channels else "email")
        choice_var = ctk.StringVar(value=default)
        opts = ctk.CTkFrame(c, fg_color="transparent")
        opts.pack(anchor="w", pady=8)
        for label, value in [("📧 Email only", "email"), ("📱 WhatsApp only", "whatsapp"), ("Both", "both")]:
            ctk.CTkRadioButton(opts, text=label, variable=choice_var, value=value,
                                text_color=T.TEXT_MUTED, font=ctk.CTkFont(size=13)).pack(anchor="w", pady=6)

        def next_step() -> None:
            choice = choice_var.get()
            self.channels = ["email", "whatsapp"] if choice == "both" else [choice]
            self.channel_index = 0
            self._start_channel(self.channels[0])

        self._footer(next_cmd=next_step, back_cmd=lambda: self._goto("welcome"))

    def _render_email_creds(self) -> None:
        mw = self.main_window
        c = self.content
        ctk.CTkLabel(c, text="📧 Email — SMTP Setup", font=ctk.CTkFont(size=17, weight="bold"),
                     text_color=T.TEXT_HEAD).pack(anchor="w", pady=(16, 4))
        ctk.CTkLabel(c, text="Credentials used to send campaigns from the Compose screen.",
                     text_color=T.TEXT_MUTED, font=ctk.CTkFont(size=12)).pack(anchor="w", pady=(0, 12))

        def on_preset(val: str) -> None:
            host, port = SMTP_PRESETS.get(val, ("", "587"))
            mw._em_host.set(host)
            mw._em_port.set(port)

        ctk.CTkLabel(c, text="Provider", text_color=T.TEXT_HEAD, font=ctk.CTkFont(size=12)).pack(anchor="w")
        ctk.CTkOptionMenu(c, values=list(SMTP_PRESETS.keys()), variable=mw._em_provider,
                          command=on_preset, fg_color=T.BG_INNER, button_color=T.BG_INNER,
                          button_hover_color=T.BG_BORDER, text_color=T.TEXT_HEAD,
                          dropdown_fg_color=T.BG_SURFACE, dropdown_hover_color=T.BG_BORDER,
                          dropdown_text_color=T.TEXT_HEAD).pack(anchor="w", fill="x", pady=(2, 10))

        fields = [
            ("Host", mw._em_host, False, "The SMTP server address your provider gives you."),
            ("Port", mw._em_port, False, "Usually 587 for Gmail/Outlook/Yahoo. If that fails, try 465."),
            ("Username", mw._em_user, False, "Usually your full email address."),
            ("Password", mw._em_pass, True,
             "For Gmail/Outlook, use an App Password, not your normal login password."),
            ("Sender name", mw._em_from_name, False, "The name recipients see, e.g. \"Acme Support\"."),
            ("Sender email", mw._em_from_addr, False, "Usually the same as Username."),
        ]
        for label, var, secret, help_text in fields:
            ctk.CTkLabel(c, text=label, text_color=T.TEXT_HEAD, font=ctk.CTkFont(size=12)).pack(anchor="w")
            ctk.CTkEntry(c, textvariable=var, show="●" if secret else "",
                         fg_color=T.BG_INNER, border_color=T.BG_BORDER,
                         text_color=T.TEXT_HEAD).pack(anchor="w", fill="x", pady=(2, 2))
            ctk.CTkLabel(c, text=help_text, text_color=T.TEXT_DIM, font=ctk.CTkFont(size=10),
                         wraplength=520, justify="left").pack(anchor="w", pady=(0, 8))

        def go_next() -> None:
            if not mw._em_host.get() or not mw._em_user.get() or not mw._em_pass.get():
                messagebox.showwarning(
                    "Missing info", "Fill in at least Host, Username, and Password.", parent=self)
                return
            mw._save_settings()
            self._goto("email_test")

        self._footer(next_cmd=go_next, back_cmd=lambda: self._goto("channel_choice"))

    def _render_email_test(self) -> None:
        mw = self.main_window
        c = self.content
        ctk.CTkLabel(c, text="Test Connection", font=ctk.CTkFont(size=17, weight="bold"),
                     text_color=T.TEXT_HEAD).pack(anchor="w", pady=(20, 4))
        ctk.CTkLabel(c, text="We'll try a real connection to your SMTP server with these credentials.",
                     text_color=T.TEXT_MUTED, font=ctk.CTkFont(size=12),
                     wraplength=520, justify="left").pack(anchor="w", pady=(0, 20))

        status_pill = ctk.CTkLabel(c, text="Not tested yet", fg_color=T.BADGE_BG, corner_radius=999,
                                    text_color=T.TEXT_MUTED, font=ctk.CTkFont(size=12, weight="bold"),
                                    padx=12, pady=6, wraplength=480, justify="left")
        status_pill.pack(anchor="w", pady=(0, 16))

        def on_result(success: bool, message: str) -> None:
            status_pill.configure(text=message, text_color=T.SUCCESS if success else T.DANGER_ON_BADGE)
            test_btn.configure(state="normal")

        def run_test() -> None:
            test_btn.configure(state="disabled")
            status_pill.configure(text="Testing…", text_color=T.TEXT_MUTED)
            mw._test_smtp_connection(on_result)

        test_btn = ctk.CTkButton(c, text="🔌 Test Connection", fg_color=T.ACCENT,
                                  hover_color=T.ACCENT_HOVER, text_color=T.TEXT_HEAD, command=run_test)
        test_btn.pack(anchor="w", pady=(0, 20))

        self._footer(next_cmd=lambda: self._goto("email_send"), back_cmd=lambda: self._goto("email_creds"))

    def _render_email_send(self) -> None:
        mw = self.main_window
        c = self.content
        ctk.CTkLabel(c, text="Send a real test email", font=ctk.CTkFont(size=17, weight="bold"),
                     text_color=T.TEXT_HEAD).pack(anchor="w", pady=(20, 4))
        ctk.CTkLabel(c, text="Confirms everything end-to-end with one real email.",
                     text_color=T.TEXT_MUTED, font=ctk.CTkFont(size=12),
                     wraplength=520, justify="left").pack(anchor="w", pady=(0, 16))

        ctk.CTkLabel(c, text="Send test to", text_color=T.TEXT_HEAD, font=ctk.CTkFont(size=12)).pack(anchor="w")
        to_var = ctk.StringVar(value=mw._em_from_addr.get())
        ctk.CTkEntry(c, textvariable=to_var, fg_color=T.BG_INNER, border_color=T.BG_BORDER,
                     text_color=T.TEXT_HEAD).pack(anchor="w", fill="x", pady=(2, 16))

        status_pill = ctk.CTkLabel(c, text="", fg_color=T.BADGE_BG, corner_radius=999,
                                    text_color=T.TEXT_MUTED, font=ctk.CTkFont(size=12, weight="bold"),
                                    padx=12, pady=6, wraplength=480, justify="left")

        def do_send() -> None:
            to_addr = to_var.get().strip()
            if not to_addr or not DataValidator.is_valid_email(to_addr):
                messagebox.showwarning(
                    "Invalid email", "Enter a valid email address to send the test to.", parent=self)
                return
            send_btn.configure(state="disabled")
            status_pill.configure(text="Sending…", text_color=T.TEXT_MUTED)
            status_pill.pack(anchor="w", pady=(0, 10))

            contact = Contact(name="Test", email=to_addr)
            html = ("<html><body style='font-family:sans-serif'>"
                    "<p>✅ This is a test message from <b>MessageCannon Pro</b>.</p>"
                    "<p>If you're reading this, your email setup works.</p></body></html>")

            def worker() -> None:
                try:
                    result = mw._send_email_campaign(
                        [(contact, "MessageCannon Pro — Setup Test ✅", html)], "Setup Wizard Test")
                    ok = result["sent"] > 0
                    msg = "✅ Test email sent!" if ok else "Send failed — check the error in History."
                except Exception as ex:
                    ok, msg = False, str(ex)
                self.after(0, lambda: finish(ok, msg))

            def finish(ok: bool, msg: str) -> None:
                send_btn.configure(state="normal")
                status_pill.configure(text=msg, text_color=T.SUCCESS if ok else T.DANGER_ON_BADGE)

            threading.Thread(target=worker, daemon=True).start()

        send_btn = ctk.CTkButton(c, text="📤 Send Test Email", fg_color=T.ACCENT,
                                  hover_color=T.ACCENT_HOVER, text_color=T.TEXT_HEAD, command=do_send)
        send_btn.pack(anchor="w", pady=(0, 10))

        self._footer(next_cmd=self._advance_after_channel_done, back_cmd=lambda: self._goto("email_test"))

    def _render_whatsapp_connect(self) -> None:
        mw = self.main_window
        c = self.content
        ctk.CTkLabel(c, text="📱 Connect WhatsApp", font=ctk.CTkFont(size=17, weight="bold"),
                     text_color=T.TEXT_HEAD).pack(anchor="w", pady=(20, 4))
        ctk.CTkLabel(c,
                     text="Clicking Connect opens a real Chrome window. On your phone, open WhatsApp → "
                          "Settings → Linked Devices → Link a Device, then scan the QR code shown.",
                     text_color=T.TEXT_MUTED, font=ctk.CTkFont(size=12),
                     wraplength=520, justify="left").pack(anchor="w", pady=(0, 20))

        status_pill = ctk.CTkLabel(c, text="Not connected", fg_color=T.BADGE_BG, corner_radius=999,
                                    text_color=T.TEXT_MUTED, font=ctk.CTkFont(size=12, weight="bold"),
                                    padx=12, pady=6, wraplength=480, justify="left")
        status_pill.pack(anchor="w", pady=(0, 16))

        def do_connect() -> None:
            connect_btn.configure(state="disabled")
            status_pill.configure(
                text="Opening WhatsApp Web — scan the QR code on your phone…", text_color=T.TEXT_MUTED)

            def worker() -> None:
                try:
                    state = mw.whatsapp_sender.initialize()
                    ok, msg = state.is_active, state.status_text
                except Exception as ex:
                    ok, msg = False, str(ex)
                self.after(0, lambda: finish(ok, msg))

            def finish(ok: bool, msg: str) -> None:
                connect_btn.configure(state="normal")
                status_pill.configure(text=msg, text_color=T.SUCCESS if ok else T.DANGER_ON_BADGE)
                if ok:
                    next_btn.configure(state="normal")

            threading.Thread(target=worker, daemon=True).start()

        connect_btn = ctk.CTkButton(c, text="🔗 Connect WhatsApp", fg_color=T.ACCENT,
                                     hover_color=T.ACCENT_HOVER, text_color=T.TEXT_HEAD, command=do_connect)
        connect_btn.pack(anchor="w", pady=(0, 10))

        next_btn = self._footer(next_cmd=lambda: self._goto("whatsapp_send"),
                                 back_cmd=lambda: self._goto("channel_choice"))
        next_btn.configure(state="disabled")

    def _render_whatsapp_send(self) -> None:
        mw = self.main_window
        c = self.content
        ctk.CTkLabel(c, text="Send a real test WhatsApp message", font=ctk.CTkFont(size=17, weight="bold"),
                     text_color=T.TEXT_HEAD).pack(anchor="w", pady=(20, 4))
        ctk.CTkLabel(c, text="Enter your own WhatsApp number (with country code) to confirm sending works.",
                     text_color=T.TEXT_MUTED, font=ctk.CTkFont(size=12),
                     wraplength=520, justify="left").pack(anchor="w", pady=(0, 16))

        ctk.CTkLabel(c, text="Your WhatsApp number", text_color=T.TEXT_HEAD,
                     font=ctk.CTkFont(size=12)).pack(anchor="w")
        phone_var = ctk.StringVar(value="")
        ctk.CTkEntry(c, textvariable=phone_var, placeholder_text="+1 555 123 4567",
                     fg_color=T.BG_INNER, border_color=T.BG_BORDER,
                     text_color=T.TEXT_HEAD).pack(anchor="w", fill="x", pady=(2, 16))

        status_pill = ctk.CTkLabel(c, text="", fg_color=T.BADGE_BG, corner_radius=999,
                                    text_color=T.TEXT_MUTED, font=ctk.CTkFont(size=12, weight="bold"),
                                    padx=12, pady=6, wraplength=480, justify="left")

        def do_send() -> None:
            raw_phone = phone_var.get().strip()
            validator = PhoneValidator()
            normalized, error = validator.normalize_phone(raw_phone)
            if not normalized:
                messagebox.showwarning(
                    "Invalid number", error or "Enter a valid phone number with country code.", parent=self)
                return
            send_btn.configure(state="disabled")
            status_pill.configure(text="Sending…", text_color=T.TEXT_MUTED)
            status_pill.pack(anchor="w", pady=(0, 10))

            contact = Contact(name="Test", phone=normalized)
            message = ("✅ This is a test message from MessageCannon Pro. "
                       "If you're reading this, WhatsApp sending works!")

            def worker() -> None:
                try:
                    result = mw.whatsapp_sender.send_messages(
                        contacts=[contact], messages=[message],
                        delay=0, use_jitter=False, max_messages=1)
                    ok = result.get("sent", 0) > 0
                    msg = "✅ Test message sent!" if ok else "Send failed — check WhatsApp connection."
                except Exception as ex:
                    ok, msg = False, str(ex)
                self.after(0, lambda: finish(ok, msg))

            def finish(ok: bool, msg: str) -> None:
                send_btn.configure(state="normal")
                status_pill.configure(text=msg, text_color=T.SUCCESS if ok else T.DANGER_ON_BADGE)

            threading.Thread(target=worker, daemon=True).start()

        send_btn = ctk.CTkButton(c, text="📤 Send Test Message", fg_color=T.ACCENT,
                                  hover_color=T.ACCENT_HOVER, text_color=T.TEXT_HEAD, command=do_send)
        send_btn.pack(anchor="w", pady=(0, 10))

        self._footer(next_cmd=self._advance_after_channel_done, back_cmd=lambda: self._goto("whatsapp_connect"))

    def _render_done(self) -> None:
        c = self.content
        ctk.CTkLabel(c, text="🎉 You're all set!", font=ctk.CTkFont(size=22, weight="bold"),
                     text_color=T.TEXT_HEAD).pack(pady=(40, 10))
        configured = ", ".join(ch.capitalize() for ch in self.channels) or "nothing yet"
        ctk.CTkLabel(c, text=f"Configured: {configured}", text_color=T.TEXT_MUTED,
                     font=ctk.CTkFont(size=13)).pack(pady=(0, 4))
        ctk.CTkLabel(c, text="You can redo this anytime from Settings → Re-run Setup Wizard.",
                     text_color=T.TEXT_DIM, font=ctk.CTkFont(size=11)).pack(pady=(0, 30))

        def finish() -> None:
            self.main_window._save_wizard_progress(setup_wizard_completed=True)
            self.main_window._refresh_setup_banner()
            self.destroy()

        ctk.CTkButton(c, text="Go to Dashboard", width=200, height=42,
                      fg_color=T.ACCENT, hover_color=T.ACCENT_HOVER, text_color=T.TEXT_HEAD,
                      font=ctk.CTkFont(size=13, weight="bold"), command=finish).pack()


def show_setup_wizard(main_window, force_restart: bool = False) -> SetupWizard:
    """Open the setup wizard, or focus it if already open."""
    existing = getattr(main_window, "_setup_wizard_dialog", None)
    if existing is not None and existing.winfo_exists():
        existing.focus()
        return existing
    wizard = SetupWizard(main_window, force_restart=force_restart)
    main_window._setup_wizard_dialog = wizard
    return wizard
