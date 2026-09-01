"""Modern CustomTkinter main window for MessageCannon."""

from __future__ import annotations

import ctypes
import html as html_module
import json
import os
import random
import re
import sys
import threading
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from tkinter import BooleanVar, IntVar, StringVar, filedialog, messagebox
from typing import Dict, List, Optional

import smtplib
import ssl
import tkinter as tk
import webbrowser
from html.parser import HTMLParser
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import customtkinter as ctk
from PIL import Image
from ..ui.card_creator_tab import build_card_creator_view, HAS_HTML_PREVIEW
from ..ui.reports_chart import ReportsChart
from ..ui.update_dialog import show_update_dialog
from ..ui.accessibility import enable_keyboard_accessibility
from ..ui.tour import install_tour_mode
from ..core.update_checker import (
    check_for_update,
    spawn_update_after_current_process_exits,
    get_installed_exe_path,
    UpdateInfo,
)

try:
    from tkinterdnd2 import TkinterDnD
    HAS_DND = True
except ImportError:
    HAS_DND = False

# Patches CTkButton/CTkSwitch/CTkCheckBox/CTkSlider at the class level so
# every one of them, app-wide, gains Enter/Space activation, arrow-key
# slider control, and a visible focus ring -- must run before any of these
# widgets are constructed, so it happens here at module import time, before
# MainWindow (or anything it imports that builds widgets) is instantiated.
enable_keyboard_accessibility()


def _ensure_tcl_tk_paths() -> None:
    """Set Tcl/Tk env vars early so direct UI imports work on Windows."""
    if os.environ.get("TCL_LIBRARY") and os.environ.get("TK_LIBRARY"):
        return

    candidate_bases = [Path(sys.base_prefix), Path(sys.executable).resolve().parent.parent]
    for base in candidate_bases:
        tcl_dir = base / "tcl" / "tcl8.6"
        tk_dir = base / "tcl" / "tk8.6"
        if tcl_dir.exists() and tk_dir.exists():
            os.environ.setdefault("TCL_LIBRARY", str(tcl_dir))
            os.environ.setdefault("TK_LIBRARY", str(tk_dir))
            return


_ensure_tcl_tk_paths()

from ..core import bounce_checker
from ..core import reputation, warmup_scheduler
from ..core import whatsapp_accounts as wa_accounts
from ..core.contact_manager import ContactManager
from ..core.message_processor import MessageProcessor
from ..core.whatsapp_sender import WhatsAppSender
from ..database.db_manager import DatabaseManager
from ..models import Contact, Template, Campaign, MessageLog, MessageStatus
from ..utils.constants import (
    APP_NAME, APP_VERSION, DEVELOPER, WINDOW_HEIGHT, WINDOW_WIDTH, JITTER_RANGE,
    BOUNCE_AUTO_CHECK_DELAY_MS,
)
from . import theme as T
from .toast import show_toast
from .window_utils import center_on_parent, center_on_screen
from .confirm_dialogs import show_danger_confirm
from .tooltip import add_tooltip
from ..core import ai_service
from ..core.ai_service import AIServiceError
from ..core.html_import import import_html_file, HtmlImportError
from ..utils.crypto import encrypt_secret, decrypt_secret
from ..utils.validators import DataValidator
from ..utils.license_manager import LicenseManager
from ..utils.logger import Logger


EMAIL_TEMPLATES = {
    # Item 10 of the Live Testing Findings pass: 3-tuples of
    # (subject, body, is_html). The 4 legacy entries below carry real,
    # richly-styled marketing HTML (gradients/colored boxes/CTA buttons) --
    # Tk has no HTML-rendering widget, so once the compose editor became a
    # real rich-text (Bold/Italic/List) editor instead of a raw-tag view,
    # these get run through _load_html_into_email_editor (a best-effort
    # HTML -> bold/italic/bullet/paragraph importer) when picked, which
    # necessarily flattens their visual chrome to plain formatted text --
    # a disclosed, user-confirmed trade-off, not a silent regression. The 4
    # new ones are defined directly as plain rich text (is_html=False) since
    # they were never HTML in the first place.
    "(none)": ("", "", False),
    "Welcome": (
        "Welcome aboard, {name}!",
        "Hi {name},\n\nWelcome aboard! We're excited to have you with us.\n\n"
        "If you have any questions, just reply to this email — we're happy to help.\n\n"
        "Best,\n{sender}",
        False,
    ),
    "Promotion": (
        "A special offer for you, {name}",
        "Hi {name},\n\nWe've got something special for you this week — {amount} off "
        "your next order.\n\nDon't miss out, this offer won't last long.\n\n"
        "Thanks,\n{sender}",
        False,
    ),
    "Reminder": (
        "Reminder: {date} is coming up",
        "Hi {name},\n\nJust a quick reminder about {date}. We wanted to make sure "
        "it's on your radar.\n\nLet us know if you need anything before then.\n\n"
        "Best,\n{sender}",
        False,
    ),
    "Follow-up": (
        "Following up, {name}",
        "Hi {name},\n\nJust checking in to see how things are going. Let us know if "
        "there's anything we can help with.\n\nLooking forward to hearing from you.\n\n"
        "Best,\n{sender}",
        False,
    ),
    "Professional": (
        "Important Update from {name}",
        """<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;border:1px solid #e0e0e0;border-radius:8px;overflow:hidden">
  <div style="background:#1a1a2e;padding:24px;text-align:center">
    <h1 style="color:#fff;margin:0;font-size:24px">MessageCannon Pro</h1>
  </div>
  <div style="padding:32px">
    <p style="font-size:16px;color:#333">Dear <strong>{name}</strong>,</p>
    <p style="font-size:15px;color:#555;line-height:1.6">We have an important update to share with you.</p>
    <p style="color:#555">Best regards,<br><strong>{sender}</strong></p>
  </div>
  <div style="background:#f9f9f9;padding:16px;text-align:center;font-size:12px;color:#999">
    To unsubscribe reply STOP.
  </div>
</div>""",
        True,
    ),
    "Promo Offer": (
        "🎉 Special Offer Just for You, {name}!",
        """<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto">
  <div style="background:#667eea;padding:40px;text-align:center">
    <h1 style="color:#fff;margin:0;font-size:28px">🎉 Special Offer</h1>
    <p style="color:rgba(255,255,255,0.9);font-size:18px">Just for you, {name}!</p>
  </div>
  <div style="padding:32px;background:#fff">
    <p style="font-size:16px;color:#333">Hi <strong>{name}</strong>,</p>
    <p style="color:#555;line-height:1.6">We have an exclusive offer waiting for you.</p>
    <div style="text-align:center;margin:32px 0">
      <a href="#" style="background:#764ba2;color:#fff;padding:14px 32px;border-radius:30px;text-decoration:none;font-size:16px;font-weight:bold">
        Claim Your Offer →
      </a>
    </div>
    <p style="color:#999;font-size:12px;text-align:center">Reply STOP to unsubscribe.</p>
  </div>
</div>""",
        True,
    ),
    "Appointment Reminder": (
        "Reminder: Your Appointment on {date}",
        """<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;border:1px solid #e0e0e0;border-radius:8px">
  <div style="background:#0f9b8e;padding:24px;text-align:center">
    <h2 style="color:#fff;margin:0">📅 Appointment Reminder</h2>
  </div>
  <div style="padding:32px">
    <p>Dear <strong>{name}</strong>,</p>
    <p>Your appointment is on <strong>{date}</strong> at <strong>{time}</strong>.</p>
    <p>Contact us if you need to reschedule.</p>
    <p>Warm regards,<br><strong>{sender}</strong></p>
  </div>
</div>""",
        True,
    ),
    "Invoice": (
        "Invoice #{invoice_no} — Amount Due: {amount}",
        """<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto">
  <div style="background:#1e3a5f;padding:24px">
    <h2 style="color:#fff;margin:0">Invoice #{invoice_no}</h2>
  </div>
  <div style="padding:32px">
    <p>Dear <strong>{name}</strong>,</p>
    <p><strong>Amount Due:</strong> {amount}</p>
    <p><strong>Due Date:</strong> {date}</p>
    <p>Thank you for your business.<br><strong>{sender}</strong></p>
  </div>
</div>""",
        True,
    ),
}

# Item 9 of the Live Testing Findings pass: readable labels for the
# "Insert variable ▾" dropdown and the pill/chip each token renders as in
# the message editors, instead of raw {token} text. Any {token} not listed
# here still gets pillified (see _label_for_variable_token below) — this map
# only supplies friendlier labels for the common ones; it is not exhaustive
# because EMAIL_TEMPLATES above already uses tokens like {sender}/{time}/
# {invoice_no} that must still render as a pill, just with a derived label.
_VARIABLE_TOKEN_LABELS = {
    "name": "Name", "email": "Email", "phone": "Phone",
    "amount": "Amount", "date": "Date",
}


def _label_for_variable_token(token: str) -> str:
    """'{name}' -> 'Name', '{invoice_no}' -> 'Invoice No' (derived fallback
    for tokens outside the common set above, e.g. from EMAIL_TEMPLATES)."""
    key = token.strip("{}")
    return _VARIABLE_TOKEN_LABELS.get(key, key.replace("_", " ").title())


class _HTMLToRichText(HTMLParser):
    """Item 10 of the Live Testing Findings pass: best-effort importer that
    loads a legacy EMAIL_TEMPLATES HTML string into the new rich-text (tag-
    based bold/italic/bullet) editor. Deliberately not a full HTML renderer
    -- Tk has none available -- so inline styles/colors/backgrounds/CTA-
    button chrome are dropped by design (a disclosed, user-confirmed trade-
    off, see the EMAIL_TEMPLATES comment above); only structure that a plain
    rich-text editor can actually represent survives: bold (<strong>/<b>/
    headings), italic (<em>/<i>), paragraph breaks, <br>, and <li> bullets.
    A link's href is kept as visible "(url)" text after its label, since a
    real clickable hyperlink has no representation in this editor either
    way -- dropping the URL entirely would lose real information, not just
    styling.
    """

    _HEADING = {"h1", "h2", "h3", "h4", "h5", "h6"}
    _BLOCK = _HEADING | {"p", "div", "tr"}
    _SKIP = {"script", "style"}

    def __init__(self, widget: tk.Text):
        super().__init__(convert_charrefs=True)
        self.widget = widget
        self._bold = 0
        self._italic = 0
        self._skip = 0
        self._href: Optional[str] = None
        self._need_break = False
        self._has_content = False

    def _tags(self) -> tuple:
        tags = []
        if self._bold:
            tags.append("b")
        if self._italic:
            tags.append("i")
        return tuple(tags)

    def handle_starttag(self, tag, attrs):
        if tag in self._SKIP:
            self._skip += 1
            return
        if self._skip:
            return
        if tag in ("strong", "b") or tag in self._HEADING:
            self._bold += 1
        if tag in ("em", "i"):
            self._italic += 1
        if tag in self._BLOCK and self._has_content:
            self._need_break = True
        if tag == "br":
            self.widget.insert("end", "\n", self._tags())
            self._has_content = True
        if tag == "li":
            if self._has_content:
                self.widget.insert("end", "\n")
            self.widget.insert("end", "• ", self._tags())
            self._has_content = True
        if tag == "a":
            for key, value in attrs:
                if key == "href":
                    self._href = value

    def handle_endtag(self, tag):
        if tag in self._SKIP:
            self._skip = max(0, self._skip - 1)
            return
        if self._skip:
            return
        if tag in ("strong", "b") or tag in self._HEADING:
            self._bold = max(0, self._bold - 1)
        if tag in ("em", "i"):
            self._italic = max(0, self._italic - 1)
        if tag in self._BLOCK:
            self._need_break = True
        if tag == "a":
            if self._href and self._href not in ("", "#"):
                self.widget.insert("end", f" ({self._href})", self._tags())
                self._has_content = True
            self._href = None

    def _last_char(self) -> str:
        content = self.widget.get("1.0", "end")
        return content[-2] if len(content) >= 2 else ""

    def handle_data(self, data):
        if self._skip:
            return
        text = re.sub(r"\s+", " ", data).strip()
        if not text:
            return
        if self._need_break:
            self.widget.insert("end", "\n\n")
            self._need_break = False
        elif self._has_content:
            # Adjacent inline elements (e.g. sibling <span>s used for a
            # price/old-price/discount-badge row) are often concatenated
            # with zero whitespace in the source HTML -- real browsers
            # still visually separate them via CSS margin/padding, but
            # flattening to plain text drops all of that. Insert a single
            # space so two text runs never silently run together (e.g.
            # "$299$59950% OFF"), without double-spacing runs that already
            # had real whitespace between them (handled above via strip()).
            last = self._last_char()
            if last and not last.isspace():
                self.widget.insert("end", " ")
        self.widget.insert("end", text, self._tags())
        self._has_content = True


class MainWindow(ctk.CTk):
    """Main application window with dashboard, contacts, compose, reports, and settings."""

    SETTINGS_KEY = "ui_preferences"
    THEME_COLOR_PAIRS = {
        "#0a1118": ("#f3f7fb", "#0a1118"),
        "#0c1620": ("#e8f0f7", "#0c1620"),
        "#0d1620": ("#edf3f8", "#0d1620"),
        "#091018": ("#eef3f7", "#091018"),
        "#101a24": ("#ffffff", "#101a24"),
        "#101f2b": ("#f6fbff", "#101f2b"),
        "#102131": ("#eaf3fb", "#102131"),
        "#111c27": ("#f7fbff", "#111c27"),
        "#111f2c": ("#f8fbff", "#111f2c"),
        "#121f2c": ("#f7fbff", "#121f2c"),
        "#0f1822": ("#f7fbff", "#0f1822"),
        "#0c141c": ("#fbfdff", "#0c141c"),
        "#101b26": ("#ffffff", "#101b26"),
        "#122331": ("#edf5fb", "#122331"),
        "#0c131b": ("#ffffff", "#0c131b"),
        "#163b34": ("#e2f5ed", "#163b34"),
        "#1f3f59": ("#e6f1fa", "#1f3f59"),
        "#3e2e18": ("#f9efde", "#3e2e18"),
        "#3d1f3b": ("#f7e9f6", "#3d1f3b"),
        "#314757": ("#c8d7e3", "#314757"),
        "#1d3448": ("#c8d9e7", "#1d3448"),
        "#1a2e3f": ("#ccdae6", "#1a2e3f"),
        "#183144": ("#c7d8e6", "#183144"),
        "#173041": ("#c7d8e6", "#173041"),
        "#163144": ("#c7d8e6", "#163144"),
        "#132330": ("#d1dbe6", "#132330"),
        "#35566f": ("#aac2d6", "#35566f"),
        "#173245": ("#dcecf8", "#173245"),
        "#244329": ("#e1f4e1", "#244329"),
        "#4a3318": ("#fbefd8", "#4a3318"),
        "#1d3545": ("#ddecf7", "#1d3545"),
        "#1b3950": ("#dfeef9", "#1b3950"),
        "#1d4a3c": ("#e3f4ec", "#1d4a3c"),
        "#203243": ("#ddeaf6", "#203243"),
        "#4e2428": ("#f7e3e5", "#4e2428"),
        "#6a2d33": ("#efcdd2", "#6a2d33"),
        "#5f2d33": ("#f7e1e5", "#5f2d33"),
        "#7d3a42": ("#efccd2", "#7d3a42"),
        "#7d3037": ("#f6dde1", "#7d3037"),
        "#a23e46": ("#efc7cd", "#a23e46"),
        "#1c6b4d": ("#dff4ea", "#1c6b4d"),
        "#24895f": ("#ccefdc", "#24895f"),
        "#7a5825": ("#f8edd8", "#7a5825"),
        "#9a6f30": ("#f2dfbf", "#9a6f30"),
        "#39b37a": ("#2f9b69", "#39b37a"),
        "#6d8798": ("#5b7384", "#6d8798"),
        "#88a0af": ("#5f7483", "#88a0af"),
        "#94b9b2": ("#4f7f77", "#94b9b2"),
        "#87a3ad": ("#5b7381", "#87a3ad"),
        "#d8ebf6": ("#25465d", "#d8ebf6"),
        "#d7f8e3": ("#21513c", "#d7f8e3"),
        "#cfe3e4": ("#34515e", "#cfe3e4"),
        "#dbe8f0": ("#355266", "#dbe8f0"),
        "#d6e3e7": ("#4f6878", "#d6e3e7"),
        "#a7bac6": ("#4f6574", "#a7bac6"),
        "#90aab6": ("#576d7a", "#90aab6"),
        "#9fb5c3": ("#5d7483", "#9fb5c3"),
        "#d5e4ea": ("#3e5969", "#d5e4ea"),
        "#dce4ee": ("#2f4a5f", "#dce4ee"),
        "#eaf3fb": ("#2f4a5f", "#eaf3fb"),
        "#6eb7d6": ("#2f7da1", "#6eb7d6"),
        "#ff7c87": ("#b24450", "#ff7c87"),
        "#8ea5af": ("#5f7481", "#8ea5af"),
        "#e0eef5": ("#36556d", "#e0eef5"),
        "#6faed2": ("#2f7ca5", "#6faed2"),
        "#def2df": ("#29553b", "#def2df"),
        "#ffe4b5": ("#7a5a1f", "#ffe4b5"),
        "#7fa9bf": ("#4d7086", "#7fa9bf"),
        "#d3e2ea": ("#426071", "#d3e2ea"),
        "#7dc59b": ("#2e7d57", "#7dc59b"),
        "#6f8796": ("#5c7280", "#6f8796"),
        "#ffd3d8": ("#8c4350", "#ffd3d8"),
        "#ffe7b3": ("#7d611e", "#ffe7b3"),
        "#b8cad6": ("#597182", "#b8cad6"),
        "#dbe9f5": ("#35566d", "#dbe9f5"),
    }
    THEME_SYNC_ATTRIBUTES = (
        "fg_color",
        "hover_color",
        "border_color",
        "text_color",
        "progress_color",
        "button_color",
        "button_hover_color",
        "dropdown_fg_color",
        "dropdown_hover_color",
        "dropdown_text_color",
        "text_color_disabled",
        "placeholder_text_color",
        "scrollbar_button_color",
        "scrollbar_button_hover_color",
    )
    LIGHT_MODE_LABEL_TEXT_COLORS = {
        "#dce4ee": "#2f4a5f",
        "#e0eef5": "#36556d",
        "#eaf3fb": "#2f4a5f",
    }

    def __init__(self):
        super().__init__()

        # Item 14 of the Live Testing Findings pass (Round 2): the real,
        # dominant root cause of the reported theme-switch flicker. Found by
        # reading CustomTkinter's own ctk_tk.py, not guessed: on Windows,
        # CTk's root window class calls _windows_set_titlebar_color() on
        # every single ctk.set_appearance_mode() call (so the native OS
        # title bar tracks the app's Dark/Light mode) -- and that method
        # calls the real tkinter withdraw()/deiconify() on the WHOLE WINDOW
        # to force the OS to redraw the title bar, confirmed directly: a
        # diagnostic script showed our own overlay frame (a direct child of
        # this window) go from mapped=1 right after being shown to
        # mapped=0 immediately after ctk.set_appearance_mode() ran -- a
        # child can only be unmapped like that if its ANCESTOR (this
        # window) was itself withdrawn. This is a whole-window blink, not
        # just individual widgets recoloring -- a much bigger visible
        # event than the widget-level update_idletasks() storm this file
        # ALSO mitigates below (_show_theme_switch_overlay et al). CTk
        # exposes exactly one documented escape hatch for this:
        # _deactivate_windows_window_header_manipulation. Disabling it
        # means the native title bar no longer actively tracks the in-app
        # theme (it follows Windows' own default instead) -- a real,
        # disclosed trade-off in exchange for eliminating the dominant
        # cause of the reported flicker.
        self._deactivate_windows_window_header_manipulation = True

        self.db = DatabaseManager()
        self.contact_manager = ContactManager()
        self.message_processor = MessageProcessor()
        self.whatsapp_sender = WhatsAppSender()
        # Item 39 v2: constructed once, reused across repeated toggle-on/
        # toggle-off cycles -- see tour.py's own module docstring.
        self.tour_mode = install_tour_mode(self)

        self.contacts: List[Contact] = []
        self.templates: List[Template] = []
        self.contact_selection_vars: Dict[str, BooleanVar] = {}
        self.sidebar_buttons: Dict[str, ctk.CTkButton] = {}
        self.sidebar_accent_bars: Dict[str, tk.Canvas] = {}
        self.sidebar_btn_frames: Dict[str, tk.Frame] = {}
        self.sidebar_nav_meta: Dict[str, tuple] = {}
        self._nav_accent_anim_after_id = None
        self._update_info = None
        self._sidebar_collapsed = False
        self.view_frames: Dict[str, ctk.CTkFrame] = {}
        self.view_containers: Dict[str, object] = {}
        self.activity_items: List[str] = []
        self.send_thread: Optional[threading.Thread] = None
        self._em_send_thread: Optional[threading.Thread] = None
        self.license_dialog: Optional[ctk.CTkToplevel] = None
        self._theme_switch_overlay: Optional[tk.Frame] = None
        self.license_locked = False
        self._active_view = "Campaigns"
        self._refresh_job: Optional[str] = None
        self._search_job: Optional[str] = None
        self._reports_chart: Optional[ReportsChart] = None
        self._last_heartbeat = time.time()
        self.brand_logo = self._load_brand_image((58, 58))
        self.header_brand_logo = self._load_brand_image((34, 34))

        self.theme_var = StringVar(value="Warm Ivory")
        self.delay_var = IntVar(value=30)
        self.daily_limit_var = IntVar(value=50)
        self.jitter_var = BooleanVar(value=True)
        self.consent_required_var = BooleanVar(value=True)
        self.consent_confirmed_var = BooleanVar(value=False)
        self.email_warmup_enabled_var = BooleanVar(value=True)
        self._email_warmup_start_date = ""  # ISO "YYYY-MM-DD", set on first real send
        self.report_format_var = StringVar(value="csv")
        self.session_status_var = StringVar(value="Checking session...")
        self.template_var = StringVar(value="Custom Message")
        self.search_var = StringVar(value="")
        self.progress_status_var = StringVar(value="Ready")
        self.license_message_var = StringVar(value="")
        self.license_status_var = StringVar(value="Checking license...")
        self.license_badge_var = StringVar(value="Trial")
        self.select_all_var = BooleanVar(value=False)
        self.sent_count_var = StringVar(value="0")
        self.delivered_count_var = StringVar(value="0")
        self.read_count_var = StringVar(value="0")
        self.failed_count_var = StringVar(value="0")
        self.delivery_rate_var = StringVar(value="0%")
        self.compose_contacts_var = StringVar(value="0 selected")
        self.compose_delay_var = StringVar(value="30 sec cadence")
        self.compose_limit_var = StringVar(value="Daily cap 50")
        self.contacts_total_var = StringVar(value="0 loaded")
        self.contacts_visible_var = StringVar(value="0 visible")
        self.contacts_search_var = StringVar(value="Directory standby")
        self.dashboard_session_detail_var = StringVar(value="Awaiting session status")
        self.dashboard_delivery_detail_var = StringVar(value="Monitoring pipeline idle")
        self.reports_feed_var = StringVar(value="No delivery events yet")
        self.settings_delay_chip_var = StringVar(value="Cadence 30 sec")
        self.settings_theme_chip_var = StringVar(value="Theme Dark")
        self.settings_guard_chip_var = StringVar(value="Guardrails On")
        self.header_context_var = StringVar(value="Persistent WhatsApp sessions, delivery analytics, and safer campaigns.")
        self.header_badge_var = StringVar(value="Enterprise Messaging Suite")
        self.activity_summary_var = StringVar(value="Awaiting campaign activity")
        self.report_period_var = StringVar(value="today")
        self.report_export_status_var = StringVar(value="CSV export ready")
        self.dashboard_week_var = StringVar(value="0")
        self.dashboard_month_var = StringVar(value="0")

        # Compose channel toggle + shared email send state
        self._compose_channel_var = StringVar(value="WhatsApp")
        self._em_provider  = StringVar(value="Gmail")
        self._em_host      = StringVar(value="smtp.gmail.com")
        self._em_port      = StringVar(value="587")
        self._em_user      = StringVar()
        self._em_pass      = StringVar()
        self._em_from_name = StringVar(value="My Business")
        self._em_from_addr = StringVar()
        self._em_delay     = StringVar(value="5")
        self._em_subj_var  = StringVar(value="Hello {name}!")
        self._em_tpl_var   = StringVar(value="(none)")
        self._ai_api_key       = StringVar()
        self._ai_provider      = StringVar(value="anthropic")
        self._ai_key_visible   = BooleanVar(value=False)
        self._ai_key_status_var = StringVar(value="No API key saved")
        self._em_stop_flag = threading.Event()
        self._em_pause_event = threading.Event()
        self._em_pause_event.set()  # set = running; cleared = paused
        self._view_anim_run_id = 0
        self._view_anim_after_id = None
        self._view_anim_container = None
        self._em_contacts_list: list = []
        self._em_count_var = StringVar(value="No email contacts imported")
        self._em_compose_count_var = StringVar(value="0 contacts with email")

        # "Send as Visual HTML Card" mode (Card Creator's Insert-into-Compose):
        # when active, _compose_em_body is locked read-only and the real
        # generated card HTML (with {variable} tokens preserved, substituted
        # per-recipient the same way as any other email template) is sent
        # as-is instead of the rich-text editor's own exported HTML -- see
        # _enter_email_card_mode/_exit_email_card_mode.
        self._compose_card_mode = False
        self._compose_card_html_template = ""

        self.title(f"{APP_NAME} v{APP_VERSION}")
        # Real bug found via live testing: geometry() alone leaves placement
        # to the window manager, which on Windows normally means the
        # top-left corner, not centered. Also: WINDOW_WIDTH/HEIGHT
        # (1100x750) are actually smaller than the minsize below
        # (1220x760) -- Tk enforces minsize immediately, so the window
        # always really opens at 1220x760 regardless of what geometry() was
        # asked for; centering math uses the real enforced size so it isn't
        # computed against a size the window will never actually be.
        MIN_W, MIN_H = 1220, 760
        center_on_screen(self, max(WINDOW_WIDTH, MIN_W), max(WINDOW_HEIGHT, MIN_H))
        self.minsize(MIN_W, MIN_H)
        self.configure(fg_color=T.BG_MAIN)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        if HAS_DND:
            try:
                TkinterDnD._require(self)
            except Exception as exc:
                Logger.warning(f"Drag-and-drop unavailable: {exc}")

        self._load_settings()
        self._apply_theme(self.theme_var.get())
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)
        self.grid_columnconfigure(1, weight=1)

        self._create_ui()
        self._build_status_bar()
        self._sync_theme_overrides()
        self._enforce_license()
        self._load_templates()
        self._reload_contacts()
        self._refresh_stats(update_text_feeds=True, update_dashboard_periods=True)
        self._refresh_preview()
        self._show_view("Campaigns")

        self.after(800, self._start_session_bootstrap)
        self.after(900, self._maybe_show_setup_wizard)
        self.after(1200, self._start_update_check)
        self.after(10000, self._periodic_refresh)
        self.after(2000, self._heartbeat_check)

    def _load_brand_image(self, size: tuple[int, int]) -> Optional[ctk.CTkImage]:
        image_path = Path(__file__).resolve().parents[1] / "assets" / "icons" / "app.png"
        if not image_path.exists():
            return None
        try:
            return ctk.CTkImage(light_image=Image.open(image_path), dark_image=Image.open(image_path), size=size)
        except Exception as exc:
            Logger.warning(f"Could not load brand image: {exc}")
            return None

    def _select_theme_value(self, value: object) -> object:
        if isinstance(value, (list, tuple)) and value:
            mode_index = 0 if ctk.get_appearance_mode().lower() == "light" else min(1, len(value) - 1)
            return value[mode_index]
        return value

    def _resolve_theme_color(self, color: object) -> object:
        color = self._select_theme_value(color)
        if not isinstance(color, str):
            return color
        if color.lower() == "transparent":
            return color

        normalized = color.lower()
        is_light_mode = ctk.get_appearance_mode().lower() == "light"
        if normalized == "gray98":
            return "#355266" if is_light_mode else "#dce4ee"
        if normalized == "gray10":
            return "#102131" if is_light_mode else "#dce4ee"
        if normalized == "gray20":
            return "#355266" if is_light_mode else "#dce4ee"
        if normalized == "gray78":
            return "#6f8796" if is_light_mode else "#a9b7c4"
        for dark_color, (light_color, dark_value) in self.THEME_COLOR_PAIRS.items():
            if normalized in {dark_color.lower(), light_color.lower(), dark_value.lower()}:
                return light_color if is_light_mode else dark_value
        return color

    # TkinterWeb (used by HtmlFrame in the card preview) has C-level Tcl state
    # that crashes fatally when winfo_children() or configure() are called on it
    # from outside. Skip these classes entirely during theme sync.
    _THEME_SYNC_SKIP_CLASSES = frozenset({"HtmlFrame", "TkinterWeb", "HtmlLabel", "HtmlText"})

    def _sync_widget_theme(self, widget: object) -> None:
        if widget.__class__.__name__ in self._THEME_SYNC_SKIP_CLASSES:
            return

        if hasattr(widget, "cget") and hasattr(widget, "configure"):
            for attr in self.THEME_SYNC_ATTRIBUTES:
                try:
                    current_value = widget.cget(attr)
                except Exception:
                    continue

                # Real bug found via direct instrumentation (not just code
                # reading): a (light, dark) tuple -- e.g. any T.token color
                # from theme.py -- is already CTk-native and auto-resolves
                # on every ctk.set_appearance_mode() call with zero extra
                # code. _resolve_theme_color's own _select_theme_value used
                # to unconditionally collapse ANY tuple down to a single
                # matching-mode string via widget.configure(), which
                # permanently replaced the dynamic tuple with a static one.
                # Since _rebuild_ui_for_theme calls this method right after
                # every full rebuild (freshly constructed widgets, correct
                # tuples), every widget's color got flattened to whichever
                # mode was active AT REBUILD TIME on its very first pass --
                # meaning a later plain Dark<->Light toggle (which doesn't
                # trigger a rebuild) silently stopped updating that widget's
                # color at all, often permanently until the next Warm Ivory
                # round-trip forced a fresh rebuild. Confirmed via a direct
                # probe: a Settings card's fg_color stayed frozen at the
                # Dark value (#2A4762) after switching to Light, both before
                # and after this method ran. Only plain strings (CTk's own
                # hardcoded "gray98"-style defaults, or a legacy
                # THEME_COLOR_PAIRS literal) actually need manual remapping
                # here -- an already-correct tuple must be left untouched.
                if isinstance(current_value, (tuple, list)):
                    continue

                resolved_value = self._resolve_theme_color(current_value)
                if (
                    attr == "text_color"
                    and widget.__class__.__name__ == "CTkLabel"
                    and ctk.get_appearance_mode().lower() == "light"
                    and isinstance(current_value, str)
                ):
                    resolved_value = self.LIGHT_MODE_LABEL_TEXT_COLORS.get(current_value.lower(), resolved_value)
                if resolved_value != current_value:
                    try:
                        widget.configure(**{attr: resolved_value})
                    except Exception:
                        pass

        if hasattr(widget, "winfo_children"):
            try:
                children = widget.winfo_children()
            except Exception:
                return
            for child in children:
                self._sync_widget_theme(child)

    def _sync_theme_overrides(self) -> None:
        self._sync_widget_theme(self)
        if self.license_dialog is not None and self.license_dialog.winfo_exists():
            self._sync_widget_theme(self.license_dialog)
        if hasattr(self, "_compose_em_body"):
            self._compose_em_body.configure(
                bg=T.resolve(T.BG_INNER), fg=T.resolve(T.TEXT_HEAD),
                insertbackground=T.resolve(T.TEXT_HEAD))

        # Raw tk.* widgets bypass CTk's automatic tuple-color resolution —
        # re-apply resolved colors explicitly on every theme toggle.
        active_view = getattr(self, "_active_view", None)
        for name, frame in self.sidebar_btn_frames.items():
            if frame.winfo_exists():
                frame.configure(bg=T.resolve(T.BG_MAIN))
        for name, bar in self.sidebar_accent_bars.items():
            if bar.winfo_exists():
                self._draw_nav_accent(bar, active=(name == active_view))
        if hasattr(self, "_reports_chart_host") and self._reports_chart_host.winfo_exists():
            self._reports_chart_host.configure(bg=T.resolve(T.BG_INNER))
        card_creator = getattr(self, "card_creator_tab", None)
        if card_creator is not None and hasattr(card_creator, "_preview_host"):
            if card_creator._preview_host.winfo_exists():
                card_creator._preview_host.configure(bg=T.resolve(T.BG_INNER))

    def _bind_scrollable_frame_mousewheel(self, scrollable_frame: ctk.CTkScrollableFrame) -> None:
        canvas = getattr(scrollable_frame, "_parent_canvas", None)
        if canvas is None:
            return

        def on_mousewheel(event) -> str | None:
            delta = 0
            if getattr(event, "num", None) == 4:
                delta = -1
            elif getattr(event, "num", None) == 5:
                delta = 1
            elif getattr(event, "delta", 0):
                delta = -int(event.delta / 120)

            if delta:
                canvas.yview_scroll(delta, "units")
                return "break"
            return None

        def bind_tree(widget: object) -> None:
            if hasattr(widget, "bind"):
                widget.bind("<MouseWheel>", on_mousewheel, add="+")
                widget.bind("<Button-4>", on_mousewheel, add="+")
                widget.bind("<Button-5>", on_mousewheel, add="+")
            if hasattr(widget, "winfo_children"):
                for child in widget.winfo_children():
                    bind_tree(child)

        bind_tree(scrollable_frame)

    SIDEBAR_WIDTH_EXPANDED = 220
    SIDEBAR_WIDTH_COLLAPSED = 72

    def _create_ui(self) -> None:
        # ── SIDEBAR — uses pack() internally to avoid CTkFrame grid row bugs ──
        self.grid_columnconfigure(
            0, minsize=self.SIDEBAR_WIDTH_COLLAPSED if self._sidebar_collapsed
            else self.SIDEBAR_WIDTH_EXPANDED)
        self.sidebar = ctk.CTkFrame(self, corner_radius=0, fg_color=T.BG_MAIN)
        self.sidebar.grid(row=0, column=0, sticky="nsew")

        # ── Brand (packed top) ────────────────────────────────────────────────
        brand_panel = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        brand_panel.pack(side="top", fill="x", padx=16, pady=(18, 12))
        brand_panel.grid_columnconfigure(1, weight=1)
        self._brand_logo_label = None
        if self.brand_logo is not None:
            self._brand_logo_label = ctk.CTkLabel(
                brand_panel, text="", image=self.brand_logo)
            self._brand_logo_label.grid(
                row=0, column=0, rowspan=2, padx=(0, 10), sticky="w")
        self._brand_title_label = ctk.CTkLabel(
            brand_panel, text="MessageCannon",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=T.TEXT_HEAD)
        self._brand_title_label.grid(row=0, column=1, sticky="w")
        # Real bug found via live feedback: this tagline was styled in
        # T.ACCENT_TEXT (this app's real, established "clickable link" color
        # -- see "Configure in Settings ->", "View recipient list ->",
        # "Get an API key ->", all real CTkButtons) with no command/binding
        # at all, so it visually implied a link/action that didn't exist.
        # It's a plain descriptor, not a navigable destination -- restyled
        # to T.TEXT_MUTED, the Design System's own token for "labels,
        # descriptions", matching how every other non-interactive
        # subtitle/caption in this app is styled.
        self._brand_subtitle_label = ctk.CTkLabel(
            brand_panel, text="Pro  |  Campaign Suite",
            text_color=T.TEXT_MUTED, font=ctk.CTkFont(size=10, weight="bold"))
        self._brand_subtitle_label.grid(row=1, column=1, sticky="w")

        # Collapse/expand toggle — a real, always-visible manual control.
        # CORRECTION (Round 2 research): the line that used to be here
        # claimed neither Career Copilot nor JobMind Match has a real
        # click-to-toggle collapse, only CSS breakpoints -- that was true
        # for Copilot (confirmed: no sidebar at all) but WRONG for JobMind
        # Match, which was never actually checked for this specific claim at
        # the time. JobMind's `.app-sidebar` has a real `.sidebar-collapse-
        # toggle` button (`styles.css:294`), a `transition: width 0.15s ease`
        # on the sidebar itself, a 180deg icon-rotation on toggle instead of
        # swapping glyphs, and state persisted to localStorage
        # (`wireSidebarCollapse`, `app.js:422`) -- see CLAUDE.md "Item 1"
        # checkpoint for what was and wasn't feasible to match from that.
        self.sidebar_collapse_btn = ctk.CTkButton(
            brand_panel, text="«", width=26, height=26, corner_radius=8,
            fg_color=T.NAV_INACTIVE, hover_color=T.BG_SURFACE,
            text_color=T.TEXT_MUTED, font=ctk.CTkFont(size=13, weight="bold"),
            command=self._toggle_sidebar_collapsed,
        )
        self.sidebar_collapse_btn.grid(row=0, column=2, rowspan=2, sticky="e")
        self._collapse_btn_tooltip = add_tooltip(
            self.sidebar_collapse_btn, "Collapse sidebar")

        # Hidden until _start_update_check finds a real newer GitHub release —
        # see CLAUDE.md "In-app update checker" for why there's no reference
        # pattern from Career Copilot to match here.
        #
        # The badge itself is packed/unpacked based on update state, but a
        # widget's pack() call always appends it to the END of its parent's
        # current top-to-bottom stacking order — packing it late (only once
        # an update is actually found, well after nav_frame and everything
        # else already packed) put it below the nav items, right above
        # "Premium Access", instead of here under the brand block. Wrapping it
        # in a slot frame that's packed exactly once, immediately, at this
        # position fixes it: the slot's position never changes, only its one
        # child's presence inside it does.
        # width=1, height=1 (not CTkFrame's ~200x200px default): this is a
        # pack()-managed child of the sidebar, so its *requested* size feeds
        # directly into the sidebar's own natural size computation. width=1
        # was already fixed for the "cold-start sidebar position bug"
        # checkpoint in CLAUDE.md, but height was missed there -- real bug
        # found via live user testing ("unnecessary blank space at the top
        # of the sidebar") and confirmed by direct widget-geometry
        # measurement: with only width=1 set, this slot silently defaulted
        # to CTkFrame's ~200px height (measured 250px on this machine's
        # 125% DPI scale) even while its one child (_update_badge_row) was
        # unmapped/hidden -- a large, empty, invisible-cause gap between the
        # brand block and the nav items whenever no update is available
        # (the common case). height=1 closes it the same way width=1 did.
        self._update_badge_slot = ctk.CTkFrame(self.sidebar, fg_color="transparent", width=1, height=1)
        self._update_badge_slot.pack(side="top", fill="x")

        # Round 2 item 2: JobMind Match's real `.sidebar-update-pill`
        # (styles.css:1243) is a gradient pill with a small pulsing dot --
        # confirmed via direct source read, not assumed. A true CSS gradient
        # fill on a CTkButton isn't achievable in Tk (no per-widget gradient
        # paint), so the badge itself keeps its existing flat
        # T.BADGE_BG/T.ACCENT treatment (already reasonably close visually);
        # the pulsing dot -- the actual attention-grabbing mechanic in
        # JobMind's design, not the gradient -- is the part that's genuinely
        # replicable and is what's new here. Kept the existing top position
        # (under the brand block) rather than moving it to a JobMind-style
        # bottom pin: that position was itself a real, tested bug fix (see
        # the comment above), and re-verifying a reposition against the
        # sidebar's fragile bottom pack-order (see the stacking-order bug
        # fixed elsewhere in this file) wasn't worth the regression risk for
        # a discoverability fix that the dot itself already addresses.
        self._update_badge_row = ctk.CTkFrame(self._update_badge_slot, fg_color="transparent")
        self._update_badge_dot = tk.Canvas(
            self._update_badge_row, width=10, height=10, highlightthickness=0,
            bg=T.resolve(T.BG_MAIN))
        self._update_badge_dot.pack(side="left", padx=(16, 6))
        self._update_badge_dot_item = self._update_badge_dot.create_oval(
            2, 2, 8, 8, fill=T.resolve(T.ACCENT), outline="")
        self._update_dot_pulse_after_id = None

        self.update_badge_var = ctk.StringVar(value="")
        # Item 29 (Final Premium Polish Pass): hover_color was T.BG_SURFACE --
        # the sole T.BADGE_BG-filled interactive element app-wide not using
        # T.BG_BORDER as its hover companion (already standardized on every
        # other BADGE_BG button/dropdown in Items 26-27). Normalized to match.
        self.sidebar_update_badge = ctk.CTkButton(
            self._update_badge_row, textvariable=self.update_badge_var,
            fg_color=T.BADGE_BG, hover_color=T.BG_BORDER,
            text_color=T.ACCENT_TEXT, corner_radius=999, height=26,
            font=ctk.CTkFont(size=10, weight="bold"),
            command=self._show_update_dialog,
        )
        self.sidebar_update_badge.pack(side="left", fill="x", expand=True, padx=(0, 16))
        if self._update_info is not None:
            self._refresh_update_badge()

        ctk.CTkFrame(self.sidebar, width=1, height=1, fg_color=T.BG_BORDER, corner_radius=0
                     ).pack(side="top", fill="x")

        # ── Bottom widgets (packed bottom first so nav fills remaining space) ──
        _bot = ctk.CTkFrame(self.sidebar, fg_color="transparent", width=1)
        _bot.pack(side="bottom", fill="x")

        self.sidebar_license_badge = ctk.CTkLabel(
            _bot, textvariable=self.license_badge_var,
            fg_color=T.BADGE_BG, corner_radius=999,
            padx=12, pady=5, text_color=T.SUCCESS,
            font=ctk.CTkFont(size=11, weight="bold"),
        )
        self.sidebar_license_badge.pack(side="bottom", anchor="w", padx=12, pady=(0, 14))

        self.sidebar_session_status_label = ctk.CTkLabel(
            _bot, textvariable=self.session_status_var,
            wraplength=190, justify="left",
            text_color=T.TEXT_MUTED, font=ctk.CTkFont(size=11))
        self.sidebar_session_status_label.pack(side="bottom", fill="x", padx=12, pady=(4, 3))

        self.sidebar_premium_panel = ctk.CTkFrame(
            _bot, fg_color=T.BG_SURFACE, corner_radius=10,
            border_width=1, border_color=T.BG_BORDER)
        self.sidebar_premium_panel.pack(side="bottom", fill="x", padx=10, pady=(0, 6))
        self.sidebar_premium_panel.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self.sidebar_premium_panel, text="Premium Access",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color=T.TEXT_HEAD).grid(row=0, column=0, padx=12, pady=(10, 2), sticky="w")
        ctk.CTkLabel(self.sidebar_premium_panel, text="Sessions  ·  Analytics  ·  Campaigns",
                     text_color=T.TEXT_MUTED, font=ctk.CTkFont(size=10),
                     ).grid(row=1, column=0, padx=12, pady=(0, 10), sticky="w")

        ctk.CTkFrame(_bot, width=1, height=1, fg_color=T.BG_BORDER, corner_radius=0
                     ).pack(side="bottom", fill="x")

        # ── Nav items (packed into middle nav_frame) ───────────────────────────
        nav_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        nav_frame.pack(side="top", fill="both", expand=True, padx=8, pady=(10, 4))

        nav_items = [
            ("Campaigns", "⊞", "Campaigns"),
            ("Contacts",  "☰", "Contacts"),
            ("Compose",   "✉", "Compose"),
            ("History",   "◈", "History"),
            ("Cards",     "❏", "Cards"),
            ("Settings",  "⚙", "Settings"),
        ]
        for view_name, icon, label in nav_items:
            btn_frame = tk.Frame(nav_frame, bg=T.resolve(T.BG_MAIN))
            btn_frame.pack(fill="x", pady=2)

            # Canvas (not Frame) so the active item can carry a two-stop
            # ACCENT->SUCCESS gradient rather than a flat fill — the closest
            # Tk-native analog to Career Copilot's pill-nav gradient underline
            # (see CLAUDE.md "Sidebar redesign" section for the full mapping).
            accent_bar = tk.Canvas(btn_frame, width=4, height=40, highlightthickness=0,
                                    bg=T.resolve(T.BG_MAIN))
            accent_bar.pack(side="left", fill="y", padx=(0, 4))

            button = ctk.CTkButton(
                btn_frame,
                text=icon if self._sidebar_collapsed else f"{icon}  {label}",
                anchor="center" if self._sidebar_collapsed else "w",
                # width=40, not CTkButton's ~140px default: btn_frame packs
                # this with fill="x", expand=True, so it still stretches to
                # fill whatever width the sidebar column actually is at
                # runtime — but an explicit small width keeps its own
                # *requested* size from dominating that column's natural-size
                # computation, same fix as the sidebar's divider frames above.
                # Without this, collapsed mode only changed the button's text
                # or centering, never its width — real bug found via winfo_
                # reqwidth() instrumentation, not just style, see CLAUDE.md
                # "cold-start sidebar position bug" checkpoint.
                width=40,
                height=40,
                corner_radius=10,
                fg_color=T.NAV_INACTIVE,
                hover_color=T.BG_SURFACE,
                border_width=1,
                border_color=T.NAV_INACTIVE,
                text_color=T.TEXT_HEAD,
                font=ctk.CTkFont(size=13),
                command=lambda name=view_name: self._show_view(name),
            )
            button.pack(side="left", fill="x", expand=True)

            self.sidebar_buttons[view_name] = button
            self.sidebar_accent_bars[view_name] = accent_bar
            self.sidebar_btn_frames[view_name] = btn_frame
            self.sidebar_nav_meta[view_name] = (icon, label)
            self._draw_nav_accent(accent_bar, active=False)

        self._apply_sidebar_collapsed_visuals()

        # ── TOP BAR (white) ────────────────────────────────────────────────
        self.content = ctk.CTkFrame(self, fg_color=T.BG_MAIN, corner_radius=0)
        self.content.grid(row=0, column=1, sticky="nsew")
        self.content.grid_rowconfigure(1, weight=1)
        self.content.grid_columnconfigure(0, weight=1)

        header = ctk.CTkFrame(self.content, corner_radius=0, fg_color=T.BG_MAIN,
                               border_width=0)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(1, weight=1)

        # Thin accent line at bottom of header
        ctk.CTkFrame(header, height=1, fg_color=T.BG_SURFACE, corner_radius=0).grid(
            row=2, column=0, columnspan=2, sticky="ew")

        # Left: page title + breadcrumb
        header_left = ctk.CTkFrame(header, fg_color="transparent")
        header_left.grid(row=0, column=0, padx=24, pady=(16, 4), sticky="w")

        self.header_title = ctk.CTkLabel(
            header_left,
            text="Campaigns",
            font=ctk.CTkFont(size=26, weight="bold"),
            text_color=T.TEXT_HEAD,
        )
        self.header_title.grid(row=0, column=0, sticky="w")

        # Breadcrumb row
        breadcrumb = ctk.CTkFrame(header, fg_color="transparent")
        breadcrumb.grid(row=1, column=0, columnspan=3, padx=24, pady=(0, 14), sticky="w")
        ctk.CTkLabel(breadcrumb, text="Home", text_color=T.TEXT_MUTED,
                     font=ctk.CTkFont(size=11)).pack(side="left")
        ctk.CTkLabel(breadcrumb, text=" › ", text_color=T.TEXT_MUTED,
                     font=ctk.CTkFont(size=11)).pack(side="left")
        self.header_subtitle = ctk.CTkLabel(
            breadcrumb,
            textvariable=self.header_context_var,
            text_color=T.TEXT_MUTED,
            font=ctk.CTkFont(size=11),
        )
        self.header_subtitle.pack(side="left")

        # Right: search + action icons
        header_right = ctk.CTkFrame(header, fg_color="transparent")
        header_right.grid(row=0, column=1, padx=24, pady=16, sticky="e")

        # Search bar
        self._header_search_var = tk.StringVar()
        search_entry = ctk.CTkEntry(
            header_right,
            textvariable=self._header_search_var,
            placeholder_text="Search…",
            width=200,
            height=34,
            corner_radius=16,
            border_color=T.BG_BORDER,
            fg_color=T.BG_MAIN,
            text_color=T.TEXT_HEAD,
        )
        search_entry.pack(side="left", padx=(0, 10))
        self._header_search_var.trace_add("write", self._on_header_search)

        # Settings shortcut icon
        ctk.CTkButton(
            header_right,
            text="⚙",
            width=34,
            height=34,
            corner_radius=16,
            fg_color=T.BADGE_BG,
            hover_color=T.BG_BORDER,
            text_color=T.ACCENT_TEXT,
            font=ctk.CTkFont(size=14),
            command=lambda: self._show_view("Settings"),
        ).pack(side="left", padx=3)

        # Item 39 v2: a permanent, always-available entry point -- not just
        # a first-run popup like the Setup Wizard -- toggles Tour Mode's
        # cursor-following "hover to discover" layer on/off (tour.py). The
        # button's own fill flips to T.ACCENT while active (TourMode.enable/
        # disable reach back into this exact widget), so it visibly shows
        # tour state, not just launches an action.
        self.header_tour_btn = ctk.CTkButton(
            header_right,
            text="?",
            width=34,
            height=34,
            corner_radius=16,
            fg_color=T.BADGE_BG,
            hover_color=T.BG_BORDER,
            text_color=T.ACCENT_TEXT,
            font=ctk.CTkFont(size=14, weight="bold"),
            command=lambda: self.tour_mode.toggle(),
        )
        self.header_tour_btn.pack(side="left", padx=3)
        add_tooltip(self.header_tour_btn,
                     "Tour Mode — hover any feature to discover what it does.")

        self.header_pill = ctk.CTkLabel(
            header_right,
            textvariable=self.header_badge_var,
            fg_color=T.BADGE_BG,
            corner_radius=999,
            padx=12,
            pady=5,
            text_color=T.ACCENT_TEXT,
            font=ctk.CTkFont(size=11, weight="bold"),
        )
        self.header_pill.pack(side="left", padx=(12, 0))

        # ── VIEW HOST (light gray) ─────────────────────────────────────────
        self.view_host = ctk.CTkFrame(self.content, fg_color=T.BG_MAIN, corner_radius=0)
        self.view_host.grid(row=1, column=0, sticky="nsew", padx=24, pady=16)
        self.view_host.grid_rowconfigure(0, weight=1)
        self.view_host.grid_columnconfigure(0, weight=1)

        self._build_campaigns_home_view()
        self._build_contacts_view()
        self._build_compose_view()
        self._build_campaign_history_view()
        self._build_settings_view()
        build_card_creator_view(self)

        # Compose has the heaviest widget tree in the app (dual WA/Email
        # panels + a live contact checkbox list) — Tk's layout cost for its
        # first-ever hidden->visible transition measured 500-670ms on its
        # own, independent of navigation animation logic (confirmed by
        # isolating grid()/update_idletasks() calls directly). Rather than
        # make the user pay that on their first real click to Compose, pay
        # it once here, hidden behind the ~1.1s startup splash screen that
        # already exists (see main.py's _show_startup_splash).
        #
        # Cards (Card Creator — Card Identity panel, live HTML preview,
        # Send Summary) turned out to need the exact same treatment, found
        # while verifying the view-stacking fix above: isolated measurement
        # (grid()+update_idletasks() alone, no animation logic) showed its
        # first-ever render costs ~350-500ms, dropping to ~70-85ms on every
        # later render — the same cold-first-render/warm-after shape as
        # Compose, just never given the same pre-warm treatment, so it sat
        # right at the edge of test_navigation_timing.py's 500ms budget.
        #
        # Unlike Compose, pre-warming Cards synchronously right here measured
        # as a no-op (0.0ms) — card_creator_tab.py populates its live preview
        # via `self.after(800, self._schedule_preview)`, so its expensive
        # content genuinely doesn't exist yet at this point in _create_ui().
        # Warming it here would just grid()/idletasks() an empty shell.
        # Deferred to `_prewarm_heavy_views` below, scheduled comfortably
        # after that 800ms timer.
        compose_container = self.view_containers.get("Compose")
        if compose_container is not None:
            compose_container.grid()
            compose_container.update_idletasks()
            compose_container.grid_remove()
        self.after(1000, self._prewarm_heavy_views)

        self.bind("<Control-n>", lambda _event: self._show_view("Compose"))
        self.bind("<Control-i>", lambda _event: self._open_import_review())
        self.bind("<Control-g>", lambda _event: self._show_view("Cards"))

    def _enforce_license(self) -> None:
        """Allow the free trial, then require a real, machine-bound activation code after expiry."""
        license_info = LicenseManager.check_license()
        self.license_info = license_info
        self.license_locked = False

        if license_info.get("is_valid") and license_info.get("is_trial"):
            self._log_activity(f"Trial active: {license_info.get('days_remaining', 0)} day(s) remaining")
            self._update_license_ui()
            return

        if license_info.get("is_valid"):
            self._log_activity("Commercial license active")
            self._update_license_ui()
            return

        self.license_locked = True
        self._update_license_ui()
        self.after(100, self._show_license_gate)

    def _show_license_gate(self) -> None:
        """Show a proper activation screen when the free trial has expired."""
        if self.license_dialog is not None and self.license_dialog.winfo_exists():
            self.license_dialog.focus()
            return

        dialog = ctk.CTkToplevel(self)
        self.license_dialog = dialog
        dialog.title("Activate MessageCannon")
        center_on_parent(dialog, 720, 520, self)
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()
        dialog.configure(fg_color=T.BG_MAIN)
        dialog.protocol("WM_DELETE_WINDOW", self._close_license_dialog_and_exit)

        dialog.grid_columnconfigure(0, weight=1)
        dialog.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(dialog, fg_color=T.BG_SURFACE, corner_radius=14)
        header.grid(row=0, column=0, padx=24, pady=(20, 12), sticky="ew")
        header.grid_columnconfigure(1, weight=1)

        crown = ctk.CTkLabel(
            header,
            text="" if self.brand_logo is not None else "MC",
            image=self.brand_logo,
            width=64,
            height=64,
            corner_radius=16,
            fg_color=T.ACCENT,
            text_color=T.TEXT_HEAD,
            font=ctk.CTkFont(size=24, weight="bold"),
        )
        crown.grid(row=0, column=0, rowspan=3, padx=(20, 14), pady=24, sticky="n")
        ctk.CTkLabel(
            header,
            text="Trial Expired",
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color=T.TEXT_HEAD,
        ).grid(row=0, column=1, padx=(0, 20), pady=(16, 4), sticky="w")
        ctk.CTkLabel(
            header,
            text="Unlock the premium workspace for persistent sessions, delivery insights, and a cleaner campaign workflow.",
            wraplength=520,
            justify="left",
            text_color=T.TEXT_MUTED,
        ).grid(row=1, column=1, padx=(0, 20), pady=(0, 8), sticky="w")

        feature_badges = ctk.CTkFrame(header, fg_color="transparent")
        feature_badges.grid(row=2, column=1, padx=(0, 16), pady=(0, 14), sticky="ew")
        for index, label in enumerate(
                ["3-Day Trial", "Session Save", "Delivery Reports", "Premium Dashboard"]):
            ctk.CTkLabel(
                feature_badges, text=label, fg_color=T.BADGE_BG,
                corner_radius=999, padx=10, pady=4,
                text_color=T.ACCENT_TEXT, font=ctk.CTkFont(size=11),
            ).grid(row=0, column=index, padx=4, pady=4, sticky="w")

        body = ctk.CTkFrame(dialog, fg_color=T.BG_SURFACE, corner_radius=14,
                            border_width=1, border_color=T.BG_BORDER)
        body.grid(row=1, column=0, padx=24, pady=(0, 14), sticky="nsew")
        body.grid_columnconfigure(0, weight=3)
        body.grid_columnconfigure(1, weight=2)
        body.grid_rowconfigure(0, weight=1)

        left_panel = ctk.CTkFrame(body, fg_color=T.BG_INNER, corner_radius=12)
        left_panel.grid(row=0, column=0, padx=(16, 8), pady=16, sticky="nsew")
        left_panel.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            left_panel,
            text="Premium Access Includes",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=T.TEXT_HEAD,
        ).grid(row=0, column=0, padx=16, pady=(16, 10), sticky="w")
        premium_points = [
            "Saved WhatsApp sessions so QR scans are not repeated on every restart",
            "Delivery and read analytics with CSV/PDF export support",
            "Modern dashboard, compose preview, and reporting workflow",
            "Safer message pacing controls with session reset and activation management",
        ]
        for index, point in enumerate(premium_points, start=1):
            ctk.CTkLabel(
                left_panel,
                text=f"✓  {point}",
                justify="left",
                wraplength=340,
                text_color=T.TEXT_MUTED,
                font=ctk.CTkFont(size=12),
            ).grid(row=index, column=0, padx=16, pady=5, sticky="w")

        stat_row = ctk.CTkFrame(left_panel, fg_color="transparent")
        stat_row.grid(row=5, column=0, padx=14, pady=(14, 16), sticky="ew")
        for index, (title, value) in enumerate([
            ("Session", "48h"),
            ("Trial",   "3 days"),
            ("Reports", "Live"),
        ]):
            card = ctk.CTkFrame(stat_row, fg_color=T.BADGE_BG, corner_radius=10)
            card.grid(row=0, column=index, padx=5, sticky="nsew")
            stat_row.grid_columnconfigure(index, weight=1)
            ctk.CTkLabel(card, text=title, text_color=T.TEXT_MUTED,
                         font=ctk.CTkFont(size=11)).pack(anchor="w", padx=12, pady=(10, 2))
            ctk.CTkLabel(card, text=value, font=ctk.CTkFont(size=15, weight="bold"),
                         text_color=T.ACCENT_TEXT).pack(anchor="w", padx=12, pady=(0, 12))

        right_panel = ctk.CTkFrame(body, fg_color=T.BG_INNER, corner_radius=12)
        right_panel.grid(row=0, column=1, padx=(8, 16), pady=16, sticky="nsew")
        right_panel.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            right_panel,
            text="Activate This Device",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=T.TEXT_HEAD,
        ).grid(row=0, column=0, padx=16, pady=(16, 6), sticky="w")
        ctk.CTkLabel(
            right_panel,
            text="Copy your device's request code below and send it to the seller. "
                 "They'll reply with an activation code unique to this device.",
            wraplength=240,
            justify="left",
            text_color=T.TEXT_MUTED,
            font=ctk.CTkFont(size=12),
        ).grid(row=1, column=0, padx=16, pady=(0, 12), sticky="w")

        # Item 36: a real, machine-bound request code -- the buyer's own
        # half of the request/activation-code handshake (see
        # utils/license_crypto.py's own docstring for the full scheme,
        # mirroring JobMind Match's proven pattern). Read-only + a Copy
        # button, same shape as JobMind's own request-code UI.
        request_row = ctk.CTkFrame(right_panel, fg_color="transparent")
        request_row.grid(row=2, column=0, padx=24, pady=(0, 4), sticky="ew")
        request_row.grid_columnconfigure(0, weight=1)
        self.license_request_code_var = StringVar(value=LicenseManager.get_request_code())
        self.license_request_entry = ctk.CTkEntry(
            request_row, textvariable=self.license_request_code_var,
            state="readonly", height=36, corner_radius=8,
            fg_color=T.BG_SURFACE, border_color=T.BG_BORDER, border_width=1,
            text_color=T.TEXT_HEAD, font=ctk.CTkFont(size=11, family="Consolas"))
        self.license_request_entry.grid(row=0, column=0, sticky="ew")
        ctk.CTkButton(
            request_row, text="Copy", width=56, height=36, corner_radius=8,
            fg_color=T.BADGE_BG, hover_color=T.BG_BORDER, text_color=T.TEXT_HEAD,
            font=ctk.CTkFont(size=11),
            command=self._copy_license_request_code,
        ).grid(row=0, column=1, padx=(6, 0))

        # Real bug found via a live-feedback audit of the sidebar tagline:
        # this is a plain informational notice, not a link or a real
        # warning (T.DANGER_ON_BADGE is this app's real warning-severity
        # color, used a few lines below for license_message_var) -- it was
        # styled in T.ACCENT_TEXT, this app's real "clickable" color, with
        # nothing to click. Restyled to T.TEXT_MUTED to match plain
        # informational text elsewhere.
        ctk.CTkLabel(
            right_panel,
            text="If you close the app without activating, the workspace remains locked until a valid activation code is entered.",
            wraplength=240,
            justify="left",
            text_color=T.TEXT_MUTED,
            font=ctk.CTkFont(size=11),
        ).grid(row=3, column=0, padx=16, pady=(8, 12), sticky="w")

        self.license_entry = ctk.CTkEntry(
            right_panel,
            placeholder_text="Enter activation code",
            height=44,
            border_width=1,
            corner_radius=8,
            fg_color=T.BG_SURFACE,
            border_color=T.BG_BORDER,
            text_color=T.TEXT_HEAD,
        )
        self.license_entry.grid(row=4, column=0, padx=24, pady=(0, 8), sticky="ew")
        self.license_entry.bind("<Return>", lambda _event: self._submit_license_activation())

        ctk.CTkLabel(
            right_panel,
            textvariable=self.license_message_var,
            # T.DANGER is fg_color-only per the Design System rules -- as
            # text_color on right_panel's BG_INNER surface it measures
            # 3.79:1, still under the 4.5:1 WCAG AA threshold.
            # T.DANGER_ON_BADGE passes at 5.69:1 on this same background.
            text_color=T.DANGER_ON_BADGE,
            wraplength=240,
            justify="left",
        ).grid(row=5, column=0, padx=24, pady=(0, 12), sticky="w")

        secure_note = ctk.CTkFrame(right_panel, fg_color=T.BADGE_BG, corner_radius=12,
                                   border_width=1, border_color=T.BG_BORDER)
        secure_note.grid(row=6, column=0, padx=24, pady=(0, 14), sticky="ew")
        # Real bug found via the same audit: a plain card heading (followed
        # by a TEXT_MUTED description right below, same as every other
        # info-card heading in this app, e.g. "Session Status" in Settings)
        # was styled in T.ACCENT_TEXT with nothing to click -- restyled to
        # T.TEXT_HEAD, the established heading color used everywhere else.
        ctk.CTkLabel(
            secure_note,
            text="Secure, machine-bound activation",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=T.TEXT_HEAD,
        ).pack(anchor="w", padx=14, pady=(12, 4))
        ctk.CTkLabel(
            secure_note,
            text="Verified offline, entirely on this device, against a real cryptographic "
                 "signature unique to this machine — never a shared code, never phoned "
                 "home.",
            justify="left",
            wraplength=220,
            text_color=T.TEXT_MUTED,
        ).pack(anchor="w", padx=14, pady=(0, 12))

        actions = ctk.CTkFrame(right_panel, fg_color="transparent")
        actions.grid(row=7, column=0, padx=24, pady=(6, 20), sticky="ew")
        actions.grid_columnconfigure(0, weight=1)

        ctk.CTkButton(
            actions,
            text="Exit App",
            fg_color=T.DANGER, hover_color=T.DANGER_HOVER,
            text_color=T.TEXT_HEAD,
            corner_radius=8,
            command=self._close_license_dialog_and_exit,
        ).grid(row=0, column=0, padx=(0, 10), sticky="w")
        ctk.CTkButton(
            actions,
            text="Activate Now",
            fg_color=T.ACCENT, hover_color=T.ACCENT_HOVER,
            text_color=T.TEXT_HEAD,
            corner_radius=8,
            command=self._submit_license_activation,
        ).grid(row=0, column=1, sticky="e")

        self._sync_widget_theme(dialog)

        dialog.after(50, self._focus_license_entry)

    def _focus_license_entry(self) -> None:
        if self.license_dialog is not None and self.license_dialog.winfo_exists():
            self.license_dialog.lift()
            self.license_dialog.attributes("-topmost", True)
            self.license_dialog.after(120, lambda: self.license_dialog.attributes("-topmost", False))
            self.license_entry.focus()

    def _copy_license_request_code(self) -> None:
        code = self.license_request_code_var.get()
        try:
            self.clipboard_clear()
            self.clipboard_append(code)
            show_toast(self, "Request code copied.", kind="success")
        except Exception:
            pass

    def _submit_license_activation(self) -> None:
        activation_code = self.license_entry.get().strip()
        if not activation_code:
            self.license_message_var.set("Activation code is required.")
            return

        result = LicenseManager.activate_license(activation_code)
        if not result.get("success"):
            self.license_message_var.set(str(result.get("message", "Activation failed")))
            self.license_entry.select_range(0, "end")
            self.license_entry.focus()
            return

        self.license_locked = False
        self.license_info = LicenseManager.check_license()
        self.license_message_var.set("")
        if self.license_dialog is not None and self.license_dialog.winfo_exists():
            self.license_dialog.grab_release()
            self.license_dialog.destroy()
        self.license_dialog = None
        show_toast(self, "Paid license activated successfully.", kind="success")
        self._log_activity("Commercial license activated")
        self._update_license_ui()
        self._start_session_bootstrap()

    def _close_license_dialog_and_exit(self) -> None:
        if self.license_dialog is not None and self.license_dialog.winfo_exists():
            self.license_dialog.grab_release()
            self.license_dialog.destroy()
        self.license_dialog = None
        self.after(0, self._on_close)

    def _build_campaigns_home_view(self) -> None:
        # Scrollable outer container: the hero card + recent-campaigns preview +
        # activity log can together exceed window height, especially on smaller
        # screens. A fixed-height frame with an inner weight=1 row silently
        # squeezes that row to ~0px when content overflows (found and fixed
        # during Phase 5 polish — real campaign data was being rendered but
        # was visually invisible). Scrolling the whole view, like Settings/
        # History/Contacts already do, guarantees every section stays visible.
        frame = self._new_view_container("Campaigns", scrollable=True)
        frame.grid_columnconfigure(0, weight=1)

        # ── Hero: new campaign + 2 summary stats ──────────────────────────────
        hero = ctk.CTkFrame(frame, fg_color=T.BG_SURFACE, corner_radius=14,
                            border_width=1, border_color=T.BG_BORDER)
        hero.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        hero.grid_columnconfigure(0, weight=1)

        top_bar = ctk.CTkFrame(hero, fg_color="transparent")
        top_bar.grid(row=0, column=0, padx=20, pady=(20, 12), sticky="ew")
        top_bar.grid_columnconfigure(0, weight=1)

        ctk.CTkButton(
            top_bar, text="+ New campaign",
            height=52, corner_radius=10,
            fg_color=T.ACCENT, hover_color=T.ACCENT_HOVER,
            text_color=T.TEXT_HEAD,
            font=ctk.CTkFont(size=15, weight="bold"),
            command=lambda: self._show_view("Compose"),
        ).grid(row=0, column=0, sticky="ew")

        stats_row = ctk.CTkFrame(hero, fg_color="transparent")
        stats_row.grid(row=1, column=0, padx=20, pady=(0, 20), sticky="ew")
        stats_row.grid_columnconfigure((0, 1), weight=1, uniform="stats")

        self.dashboard_cards: Dict[str, ctk.CTkLabel] = {}
        self.dashboard_card_meta: Dict[str, ctk.CTkLabel] = {}

        for col, (label_text, var_key, meta_text) in enumerate([
            ("Sent this week", "Sent Today", "Messages delivered"),
            ("Delivered",      "Delivery Rate", "Successful receipts"),
        ]):
            stat_box = ctk.CTkFrame(stats_row, fg_color=T.BG_INNER, corner_radius=10,
                                    border_width=1, border_color=T.BG_BORDER)
            stat_box.grid(row=0, column=col, padx=(0 if col else 0, 8 if col == 0 else 0),
                          sticky="ew")
            stat_box.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(stat_box, text=label_text, text_color=T.TEXT_MUTED,
                         font=ctk.CTkFont(size=11)).grid(
                row=0, column=0, padx=16, pady=(12, 2), sticky="w")
            val_lbl = ctk.CTkLabel(stat_box, text="0",
                                   font=ctk.CTkFont(size=28, weight="bold"),
                                   text_color=T.TEXT_HEAD)
            val_lbl.grid(row=1, column=0, padx=16, pady=(0, 12), sticky="w")
            meta_lbl = ctk.CTkLabel(stat_box, text=meta_text, text_color=T.TEXT_MUTED,
                                    font=ctk.CTkFont(size=10))
            meta_lbl.grid(row=1, column=1, padx=(0, 12), pady=(0, 12), sticky="se")
            self.dashboard_cards[var_key] = val_lbl
            self.dashboard_card_meta[var_key] = meta_lbl

            # Item 37 (UI/UX benchmark pass vs premium tools): a real
            # 7-day send-volume sparkline on the primary stat card --
            # premium dashboards (Klaviyo/Mailchimp-class) show a trend
            # next to a raw number; this app previously only ever showed a
            # single static count with no sense of trajectory. Real data
            # only (db.get_daily_sent_counts) -- never a decorative fake
            # trend line.
            if col == 0:
                self.dashboard_sparkline = tk.Canvas(
                    stat_box, height=28, highlightthickness=0,
                    bg=T.resolve(T.BG_INNER))
                self.dashboard_sparkline.grid(
                    row=2, column=0, columnspan=2, padx=16, pady=(0, 12), sticky="ew")

        # Placeholder row, always present — populated/cleared by
        # _refresh_setup_banner() since setup_wizard_skipped can flip to True
        # *during* this session (wizard closed after the view was already built).
        self.setup_banner_container = ctk.CTkFrame(hero, fg_color="transparent")
        self.setup_banner_container.grid(row=2, column=0, sticky="ew")
        self.setup_banner_container.grid_columnconfigure(0, weight=1)
        self._refresh_setup_banner()

        # Compat stubs so _refresh_stats doesn't crash on old card keys
        for stub_key in ("Active Session", "License State"):
            self.dashboard_cards.setdefault(stub_key, ctk.CTkLabel(frame, text=""))
            self.dashboard_card_meta.setdefault(stub_key, ctk.CTkLabel(frame, text=""))

        # ── Recent campaigns list ─────────────────────────────────────────────
        list_hdr = ctk.CTkFrame(frame, fg_color="transparent")
        list_hdr.grid(row=1, column=0, sticky="ew", pady=(0, 6))
        list_hdr.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(list_hdr, text="Recent campaigns",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=T.TEXT_HEAD).grid(row=0, column=0, sticky="w")
        ctk.CTkButton(list_hdr, text="View all", width=80, height=28,
                      corner_radius=6, fg_color=T.BADGE_BG, hover_color=T.BG_BORDER,
                      text_color=T.ACCENT_TEXT, font=ctk.CTkFont(size=11),
                      command=lambda: self._show_view("History"),
                      ).grid(row=0, column=1, sticky="e")

        list_card = ctk.CTkFrame(frame, fg_color=T.BG_SURFACE, corner_radius=14,
                                 border_width=1, border_color=T.BG_BORDER)
        list_card.grid(row=2, column=0, sticky="ew")
        list_card.grid_columnconfigure(0, weight=1)

        # Plain frame, not a nested CTkScrollableFrame: the outer view now
        # scrolls as a whole (see _new_view_container(scrollable=True) above),
        # and this preview is already capped at 10 rows via
        # get_recent_campaigns_summary(limit=10) — "View all" opens the real,
        # independently-scrollable History list for anything beyond that.
        self.home_campaigns_scroll = ctk.CTkFrame(list_card, fg_color="transparent", corner_radius=0)
        self.home_campaigns_scroll.grid(row=0, column=0, sticky="ew", padx=12, pady=12)
        self.home_campaigns_scroll.grid_columnconfigure(0, weight=1)

        # Activity log — visible at row 3
        act_hdr = ctk.CTkFrame(frame, fg_color="transparent")
        act_hdr.grid(row=3, column=0, sticky="ew", pady=(12, 4))
        act_hdr.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(act_hdr, text="Activity log",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=T.TEXT_HEAD).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(act_hdr, textvariable=self.activity_summary_var,
                     text_color=T.TEXT_MUTED, font=ctk.CTkFont(size=11)).grid(
            row=0, column=1, sticky="e")

        act_card = ctk.CTkFrame(frame, fg_color=T.BG_SURFACE, corner_radius=14,
                                border_width=1, border_color=T.BG_BORDER)
        act_card.grid(row=4, column=0, sticky="ew")
        act_card.grid_columnconfigure(0, weight=1)

        self.activity_text = ctk.CTkTextbox(
            act_card, fg_color=T.BG_INNER, text_color=T.TEXT_MUTED,
            font=ctk.CTkFont(size=11), height=110, corner_radius=10,
            border_width=1, border_color=T.BG_BORDER, state="disabled")
        self.activity_text.grid(row=0, column=0, padx=12, pady=12, sticky="ew")

        self._refresh_campaigns_home()

    def _refresh_campaigns_home(self) -> None:
        if not hasattr(self, "home_campaigns_scroll"):
            return
        scroll = self.home_campaigns_scroll
        for w in scroll.winfo_children():
            w.destroy()
        try:
            campaigns = self.db.get_recent_campaigns_summary(limit=10)
        except Exception:
            campaigns = []
        if not campaigns:
            empty = ctk.CTkFrame(scroll, fg_color=T.BG_INNER, corner_radius=12,
                                 border_width=1, border_color=T.BG_BORDER)
            empty.grid(row=0, column=0, sticky="ew", padx=6, pady=6)
            ctk.CTkLabel(empty, text="No campaigns yet",
                         font=ctk.CTkFont(size=14, weight="bold"),
                         text_color=T.TEXT_HEAD).pack(padx=16, pady=(16, 4), anchor="w")
            ctk.CTkLabel(empty, text="Start one with '+ New campaign' above.",
                         text_color=T.TEXT_MUTED).pack(padx=16, pady=(0, 16), anchor="w")
            return
        STATUS_COLORS = {"sent": T.SUCCESS, "failed": T.DANGER, "draft": T.TEXT_MUTED}
        for i, camp in enumerate(campaigns):
            row = ctk.CTkFrame(scroll, fg_color=T.BG_INNER, corner_radius=10,
                               border_width=1, border_color=T.BG_BORDER)
            row.grid(row=i, column=0, sticky="ew", pady=4)
            row.grid_columnconfigure(1, weight=1)
            name = camp.get("name", "Untitled")
            created = camp.get("created_at", "")
            sent = camp.get("sent_count", 0)
            failed = camp.get("failed_count", 0)
            status = "sent" if sent > 0 else "failed" if failed > 0 else "draft"
            ctk.CTkLabel(row, text=name, font=ctk.CTkFont(size=13, weight="bold"),
                         text_color=T.TEXT_HEAD).grid(
                row=0, column=0, padx=14, pady=(10, 2), sticky="w")
            ctk.CTkLabel(row, text=created, text_color=T.TEXT_MUTED,
                         font=ctk.CTkFont(size=11)).grid(
                row=1, column=0, padx=14, pady=(0, 10), sticky="w")
            ctk.CTkLabel(row, text=f"{sent} sent  ·  {failed} failed",
                         text_color=T.TEXT_MUTED, font=ctk.CTkFont(size=11)).grid(
                row=1, column=1, padx=14, pady=(0, 10), sticky="e")
            ctk.CTkLabel(row, text=status, fg_color=T.BADGE_BG, corner_radius=999,
                         padx=10, pady=4, text_color=STATUS_COLORS.get(status, T.TEXT_MUTED),
                         font=ctk.CTkFont(size=10)).grid(
                row=0, column=1, padx=14, pady=(10, 2), sticky="e")

    def _build_contacts_view(self) -> None:
        frame = self._new_view_frame("Contacts")
        frame.grid_rowconfigure(3, weight=1)
        frame.grid_columnconfigure(0, weight=1)

        hero = ctk.CTkFrame(frame, fg_color=T.BG_SURFACE, corner_radius=14,
                             border_width=1, border_color=T.BG_BORDER)
        hero.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        hero.grid_columnconfigure(1, weight=1)

        hero_left = ctk.CTkFrame(hero, fg_color="transparent")
        hero_left.grid(row=0, column=0, padx=16, pady=14, sticky="w")
        ctk.CTkLabel(hero_left, text="Contacts Directory",
                     font=ctk.CTkFont(size=15, weight="bold"),
                     text_color=T.TEXT_HEAD).pack(anchor="w")
        ctk.CTkLabel(hero_left, textvariable=self.contacts_search_var,
                     text_color=T.TEXT_MUTED, font=ctk.CTkFont(size=12)).pack(anchor="w", pady=(2, 0))

        hero_stats = ctk.CTkFrame(hero, fg_color="transparent")
        hero_stats.grid(row=0, column=1, padx=16, pady=14, sticky="e")
        for index, variable in enumerate([self.contacts_total_var, self.contacts_visible_var]):
            ctk.CTkLabel(hero_stats, textvariable=variable, fg_color=T.BADGE_BG,
                         corner_radius=999, padx=12, pady=6,
                         text_color=T.ACCENT_TEXT, font=ctk.CTkFont(size=11, weight="bold"),
                         ).grid(row=0, column=index, padx=6)

        toolbar = ctk.CTkFrame(frame, fg_color=T.BG_SURFACE, corner_radius=14,
                               border_width=1, border_color=T.BG_BORDER)
        toolbar.grid_columnconfigure(3, weight=1)
        toolbar.grid(row=1, column=0, sticky="ew", pady=(0, 12))

        ctk.CTkButton(toolbar, text="Import Contacts",
                      corner_radius=8, fg_color=T.BADGE_BG, hover_color=T.BG_BORDER,
                      text_color=T.TEXT_HEAD, command=self._open_import_review).grid(
            row=0, column=0, padx=12, pady=12)
        ctk.CTkButton(toolbar, text="Export CSV", corner_radius=8,
                      fg_color=T.ACCENT, hover_color=T.ACCENT_HOVER,
                      text_color=T.TEXT_HEAD,
                      command=self._export_contacts_csv).grid(
            row=0, column=1, padx=(0, 12), pady=12)
        ctk.CTkButton(toolbar, text="Refresh", corner_radius=8,
                      fg_color=T.BADGE_BG, hover_color=T.BG_BORDER,
                      text_color=T.TEXT_HEAD,
                      command=self._reload_contacts).grid(
            row=0, column=2, padx=(0, 12), pady=12)
        search_entry = ctk.CTkEntry(
            toolbar, textvariable=self.search_var,
            placeholder_text="Search by name or phone…",
            corner_radius=8, border_color=T.BG_BORDER, fg_color=T.BG_INNER,
            text_color=T.TEXT_HEAD)
        search_entry.grid(row=0, column=3, padx=(0, 12), pady=12, sticky="ew")
        search_entry.bind("<KeyRelease>", lambda _event: self._schedule_contact_search())

        self.contacts_summary_label = ctk.CTkLabel(frame, text="0 contacts loaded",
                                                   text_color=T.TEXT_MUTED,
                                                   font=ctk.CTkFont(size=12))
        self.contacts_summary_label.grid(row=2, column=0, sticky="w", padx=4, pady=(0, 6))

        self.contacts_directory = ctk.CTkScrollableFrame(
            frame, fg_color=T.BG_SURFACE, corner_radius=14,
            border_width=1, border_color=T.BG_BORDER)
        self.contacts_directory.grid(row=3, column=0, sticky="nsew")
        self._bind_scrollable_frame_mousewheel(self.contacts_directory)

    def _build_compose_view(self) -> None:
        frame = self._new_view_frame("Compose")
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(1, weight=1)

        # ── Row 0: Channel toggle bar ──────────────────────────────────────────
        ch_bar = ctk.CTkFrame(frame, fg_color=T.BG_SURFACE, corner_radius=14,
                              border_width=1, border_color=T.BG_BORDER)
        ch_bar.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        ch_bar.grid_columnconfigure(1, weight=1)

        ctk.CTkSegmentedButton(
            ch_bar, values=["WhatsApp", "Email"],
            variable=self._compose_channel_var,
            command=self._on_channel_switch,
            fg_color=T.BG_INNER,
            selected_color=T.ACCENT, selected_hover_color=T.ACCENT_HOVER,
            unselected_color=T.BG_INNER, unselected_hover_color=T.BG_SURFACE,
            text_color=T.TEXT_HEAD, font=ctk.CTkFont(size=13),
        ).grid(row=0, column=0, padx=16, pady=12, sticky="w")

        ch_meta = ctk.CTkFrame(ch_bar, fg_color="transparent")
        ch_meta.grid(row=0, column=1, padx=(0, 16), pady=12, sticky="e")
        self.compose_contacts_chip = ctk.CTkLabel(
            ch_meta, textvariable=self.compose_contacts_var, fg_color=T.BADGE_BG,
            corner_radius=999, padx=12, pady=5, text_color=T.ACCENT_TEXT, font=ctk.CTkFont(size=11))
        self.compose_contacts_chip.pack(side="left", padx=4)
        self.compose_delay_chip = ctk.CTkLabel(
            ch_meta, textvariable=self.compose_delay_var, fg_color=T.BADGE_BG,
            corner_radius=999, padx=12, pady=5, text_color=T.ACCENT_TEXT, font=ctk.CTkFont(size=11))
        self.compose_delay_chip.pack(side="left", padx=4)
        self.compose_limit_chip = ctk.CTkLabel(
            ch_meta, textvariable=self.compose_limit_var, fg_color=T.BADGE_BG,
            corner_radius=999, padx=12, pady=5, text_color=T.ACCENT_TEXT, font=ctk.CTkFont(size=11))
        self.compose_limit_chip.pack(side="left", padx=4)

        # ── Row 1a: WhatsApp panel (shown by default) ──────────────────────────
        self._wa_compose_frame = ctk.CTkFrame(frame, fg_color="transparent", corner_radius=0)
        self._wa_compose_frame.grid(row=1, column=0, sticky="nsew")
        self._wa_compose_frame.grid_columnconfigure(0, weight=3)
        self._wa_compose_frame.grid_columnconfigure(1, weight=2)
        self._wa_compose_frame.grid_rowconfigure(1, weight=1)

        wa_top = ctk.CTkFrame(self._wa_compose_frame, fg_color=T.BG_SURFACE, corner_radius=14,
                              border_width=1, border_color=T.BG_BORDER)
        wa_top.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        wa_top.grid_columnconfigure(3, weight=1)

        ctk.CTkLabel(wa_top, text="Template", text_color=T.TEXT_HEAD).grid(
            row=0, column=0, padx=(16, 8), pady=14, sticky="w")
        self.template_menu = ctk.CTkOptionMenu(
            wa_top, values=["Custom Message"],
            variable=self.template_var, command=self._on_template_selected,
            fg_color=T.BG_INNER, button_color=T.BG_INNER,
            button_hover_color=T.BG_BORDER, text_color=T.TEXT_HEAD,
            dropdown_fg_color=T.BG_SURFACE, dropdown_hover_color=T.BG_BORDER,
            dropdown_text_color=T.TEXT_HEAD,
        )
        self.template_menu.grid(row=0, column=1, padx=(0, 12), pady=14, sticky="w")
        ctk.CTkCheckBox(wa_top, text="Select all contacts", variable=self.select_all_var,
                        command=self._toggle_select_all,
                        fg_color=T.ACCENT, border_color=T.ACCENT,
                        hover_color=T.ACCENT_HOVER, checkmark_color=T.TEXT_HEAD,
                        corner_radius=4, text_color=T.TEXT_HEAD).grid(
            row=0, column=2, padx=(0, 12), pady=14, sticky="w")
        ctk.CTkCheckBox(wa_top, text="Consent confirmed", variable=self.consent_confirmed_var,
                        fg_color=T.ACCENT, border_color=T.ACCENT,
                        hover_color=T.ACCENT_HOVER, checkmark_color=T.TEXT_HEAD,
                        corner_radius=4, text_color=T.TEXT_HEAD).grid(
            row=0, column=3, padx=(0, 16), pady=14, sticky="e")

        wa_ai_row = ctk.CTkFrame(wa_top, fg_color="transparent")
        wa_ai_row.grid(row=1, column=0, columnspan=4, padx=16, pady=(0, 14), sticky="w")
        self.wa_generate_ai_btn = ctk.CTkButton(
            wa_ai_row, text="✨ Generate with AI", height=30, corner_radius=8,
            fg_color=T.ACCENT, hover_color=T.ACCENT_HOVER, text_color=T.TEXT_HEAD,
            font=ctk.CTkFont(size=11, weight="bold"),
            command=lambda: self._open_ai_compose("whatsapp"))
        self.wa_generate_ai_btn.pack(side="left", padx=(0, 8))
        ctk.CTkButton(wa_ai_row, text="💾 Save as Template", height=30, corner_radius=8,
                      fg_color=T.BADGE_BG, hover_color=T.BG_BORDER, text_color=T.TEXT_HEAD,
                      font=ctk.CTkFont(size=11),
                      command=lambda: self._open_save_template("whatsapp")).pack(side="left")

        editor_frame = ctk.CTkFrame(self._wa_compose_frame, fg_color=T.BG_SURFACE, corner_radius=14,
                                    border_width=1, border_color=T.BG_BORDER)
        editor_frame.grid(row=1, column=0, sticky="nsew", padx=(0, 8))
        editor_frame.grid_columnconfigure(0, weight=1)
        editor_frame.grid_rowconfigure(2, weight=1)
        editor_frame.grid_rowconfigure(5, weight=1)

        ctk.CTkLabel(editor_frame, text="Message editor",
                     font=ctk.CTkFont(size=15, weight="bold"),
                     text_color=T.TEXT_HEAD).grid(
            row=0, column=0, padx=16, pady=(16, 8), sticky="w")

        variables_row = ctk.CTkFrame(editor_frame, fg_color="transparent")
        variables_row.grid(row=1, column=0, padx=14, pady=(0, 12), sticky="ew")
        self.wa_insert_variable_menu = self._build_insert_variable_menu(
            variables_row, ["Name", "Phone", "Amount", "Date", "Email"],
            lambda label: self._insert_variable_label(self.message_textbox, label))
        self.wa_insert_variable_menu.grid(row=0, column=0, sticky="w")

        self.message_textbox = ctk.CTkTextbox(editor_frame, fg_color=T.BG_INNER,
                                              text_color=T.TEXT_HEAD,
                                              border_width=1, border_color=T.BG_BORDER,
                                              wrap="word")
        self.message_textbox.grid(row=2, column=0, padx=16, pady=(0, 6), sticky="nsew")
        self.message_textbox.bind("<KeyRelease>", lambda _event: self._on_wa_message_changed())

        self._wa_warning_var = StringVar(value="")
        ctk.CTkLabel(editor_frame, textvariable=self._wa_warning_var, text_color=T.TEXT_DIM,
                     font=ctk.CTkFont(size=11), wraplength=520, justify="left").grid(
            row=3, column=0, padx=16, pady=(0, 8), sticky="w")

        ctk.CTkLabel(editor_frame, text="Contacts",
                     font=ctk.CTkFont(size=14, weight="bold"),
                     text_color=T.TEXT_HEAD).grid(
            row=4, column=0, padx=16, pady=(0, 6), sticky="w")
        self.compose_contacts_frame = ctk.CTkScrollableFrame(
            editor_frame, fg_color=T.BG_INNER, corner_radius=10,
            border_width=1, border_color=T.BG_BORDER)
        self.compose_contacts_frame.grid(row=5, column=0, padx=16, pady=(0, 16), sticky="nsew")
        self._bind_scrollable_frame_mousewheel(self.compose_contacts_frame)

        preview_frame = ctk.CTkFrame(self._wa_compose_frame, fg_color=T.BG_SURFACE, corner_radius=14,
                                     border_width=1, border_color=T.BG_BORDER)
        preview_frame.grid(row=1, column=1, sticky="nsew")
        preview_frame.grid_rowconfigure(2, weight=1)
        preview_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(preview_frame, text="Preview",
                     font=ctk.CTkFont(size=15, weight="bold"),
                     text_color=T.TEXT_HEAD).grid(
            row=0, column=0, padx=16, pady=(16, 8), sticky="w")
        preview_chips = ctk.CTkFrame(preview_frame, fg_color="transparent")
        preview_chips.grid(row=0, column=0, padx=16, pady=(14, 8), sticky="e")
        ctk.CTkLabel(preview_chips, text="Live render", fg_color=T.BADGE_BG,
                     corner_radius=999, padx=10, pady=4,
                     text_color=T.ACCENT_TEXT, font=ctk.CTkFont(size=11)).grid(row=0, column=0, padx=4)
        ctk.CTkLabel(preview_chips, text="First 3 contacts", fg_color=T.BADGE_BG,
                     corner_radius=999, padx=10, pady=4,
                     text_color=T.ACCENT_TEXT, font=ctk.CTkFont(size=11)).grid(row=0, column=1, padx=4)
        ctk.CTkLabel(preview_frame, text="Preview for the first 3 selected contacts",
                     text_color=T.TEXT_MUTED, font=ctk.CTkFont(size=11)).grid(
            row=1, column=0, padx=16, pady=(0, 8), sticky="w")
        self.preview_text = ctk.CTkTextbox(preview_frame, fg_color=T.BG_INNER,
                                           text_color=T.TEXT_HEAD,
                                           border_width=1, border_color=T.BG_BORDER,
                                           wrap="word")
        self.preview_text.grid(row=2, column=0, padx=16, pady=(0, 16), sticky="nsew")

        # ── Row 1b: Email panel (hidden initially) ─────────────────────────────
        self._em_compose_frame = ctk.CTkFrame(frame, fg_color="transparent", corner_radius=0)
        self._em_compose_frame.grid(row=1, column=0, sticky="nsew")
        self._em_compose_frame.grid_remove()
        self._em_compose_frame.grid_columnconfigure(0, weight=3)
        self._em_compose_frame.grid_columnconfigure(1, weight=2)
        self._em_compose_frame.grid_rowconfigure(2, weight=1)

        # Email left column — compose area
        em_left = ctk.CTkFrame(self._em_compose_frame, fg_color=T.BG_SURFACE, corner_radius=14,
                               border_width=1, border_color=T.BG_BORDER)
        em_left.grid(row=0, column=0, rowspan=3, sticky="nsew", padx=(0, 8))
        em_left.grid_columnconfigure(0, weight=1)
        em_left.grid_rowconfigure(5, weight=1)

        ctk.CTkLabel(em_left, text="Email compose",
                     font=ctk.CTkFont(size=15, weight="bold"),
                     text_color=T.TEXT_HEAD).grid(row=0, column=0, padx=16, pady=(16, 8), sticky="w")

        em_fields = ctk.CTkFrame(em_left, fg_color="transparent")
        em_fields.grid(row=1, column=0, padx=16, pady=(0, 8), sticky="ew")
        em_fields.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(em_fields, text="Template", text_color=T.TEXT_MUTED,
                     font=ctk.CTkFont(size=11)).grid(row=0, column=0, padx=(0, 8), pady=(0, 6), sticky="w")

        def _on_em_tpl(val):
            subj, body, is_html = EMAIL_TEMPLATES.get(val, ("", "", False))
            if subj:
                self._em_subj_var.set(subj)
            if hasattr(self, "_compose_em_body"):
                self._compose_em_body.delete("1.0", "end")
                if is_html:
                    self._load_html_into_email_editor(body)
                elif body:
                    self._compose_em_body.insert("1.0", body)
                self._update_email_warnings()
                self._refresh_email_preview()

        self.em_template_menu = ctk.CTkOptionMenu(
            em_fields, values=list(EMAIL_TEMPLATES.keys()),
            variable=self._em_tpl_var, command=_on_em_tpl,
            fg_color=T.BG_INNER, button_color=T.BG_INNER,
            button_hover_color=T.BG_BORDER, text_color=T.TEXT_HEAD,
            dropdown_fg_color=T.BG_SURFACE, dropdown_hover_color=T.BG_BORDER,
            dropdown_text_color=T.TEXT_HEAD)
        self.em_template_menu.grid(row=0, column=1, pady=(0, 6), sticky="ew")

        ctk.CTkLabel(em_fields, text="Subject", text_color=T.TEXT_MUTED,
                     font=ctk.CTkFont(size=11)).grid(row=1, column=0, padx=(0, 8), sticky="w")
        subj_row = ctk.CTkFrame(em_fields, fg_color="transparent")
        subj_row.grid(row=1, column=1, sticky="ew")
        subj_row.grid_columnconfigure(0, weight=1)
        ctk.CTkEntry(subj_row, textvariable=self._em_subj_var,
                     fg_color=T.BG_INNER, border_color=T.BG_BORDER,
                     text_color=T.TEXT_HEAD).grid(row=0, column=0, sticky="ew")
        # Item 34 (sub-item 1): AI-powered subject line optimizer -- given
        # the already-drafted body, suggests 3 alternatives optimized for
        # open rates with a rationale each, building on the existing spam-
        # word/subject-length warnings (which only ever flag problems).
        self._subject_optimize_btn = ctk.CTkButton(
            subj_row, text="✨ Optimize", width=1, height=26, corner_radius=6,
            fg_color=T.BADGE_BG, hover_color=T.BG_BORDER, text_color=T.ACCENT_TEXT,
            font=ctk.CTkFont(size=10, weight="bold"),
            command=self._open_subject_optimizer)
        self._subject_optimize_btn.grid(row=0, column=1, padx=(6, 0))

        em_chips = ctk.CTkFrame(em_left, fg_color="transparent")
        em_chips.grid(row=2, column=0, padx=16, pady=(6, 8), sticky="w")
        self.em_insert_variable_menu = self._build_insert_variable_menu(
            em_chips, ["Name", "Email", "Amount", "Date"],
            lambda label: self._insert_variable_label(self._compose_em_body, label))
        self.em_insert_variable_menu.grid(row=0, column=0, sticky="w")

        # Item 10 of the Live Testing Findings pass: a real formatting
        # toolbar for the rich-text (tag-based) editor below, standing in
        # for the raw <strong>/<em>/<li> tags the editor used to show
        # literally. Only operates on an actual text selection -- a simple,
        # scoped toolbar, not a full word processor.
        fmt_row = ctk.CTkFrame(em_chips, fg_color="transparent")
        fmt_row.grid(row=0, column=1, padx=(10, 0), sticky="w")
        self._em_fmt_bold_btn = ctk.CTkButton(
            fmt_row, text="B", width=28, height=28, corner_radius=6,
            fg_color=T.BADGE_BG, hover_color=T.BG_BORDER, text_color=T.TEXT_HEAD,
            font=ctk.CTkFont(size=13, weight="bold"),
            command=lambda: self._toggle_email_char_tag("b"))
        self._em_fmt_bold_btn.pack(side="left", padx=(0, 4))
        self._em_fmt_italic_btn = ctk.CTkButton(
            fmt_row, text="I", width=28, height=28, corner_radius=6,
            fg_color=T.BADGE_BG, hover_color=T.BG_BORDER, text_color=T.TEXT_HEAD,
            font=ctk.CTkFont(size=13, weight="bold", slant="italic"),
            command=lambda: self._toggle_email_char_tag("i"))
        self._em_fmt_italic_btn.pack(side="left", padx=(0, 4))
        self._em_fmt_list_btn = ctk.CTkButton(
            fmt_row, text="≡ List", width=48, height=28, corner_radius=6,
            fg_color=T.BADGE_BG, hover_color=T.BG_BORDER, text_color=T.TEXT_HEAD,
            font=ctk.CTkFont(size=11),
            command=self._toggle_email_bullet_list)
        self._em_fmt_list_btn.pack(side="left")
        self._em_card_mode_controls = [
            self._em_fmt_bold_btn, self._em_fmt_italic_btn, self._em_fmt_list_btn,
            self.em_insert_variable_menu, self.em_template_menu,
        ]

        em_ai_row = ctk.CTkFrame(em_left, fg_color="transparent")
        em_ai_row.grid(row=3, column=0, padx=16, pady=(0, 4), sticky="ew")
        self.em_generate_ai_btn = ctk.CTkButton(
            em_ai_row, text="✨ Generate with AI", height=30, corner_radius=8,
            fg_color=T.ACCENT, hover_color=T.ACCENT_HOVER, text_color=T.TEXT_HEAD,
            font=ctk.CTkFont(size=11, weight="bold"),
            command=lambda: self._open_ai_compose("email"))
        self.em_generate_ai_btn.pack(side="left", padx=(0, 8))
        ctk.CTkButton(em_ai_row, text="💾 Save as Template", height=30, corner_radius=8,
                      fg_color=T.BADGE_BG, hover_color=T.BG_BORDER, text_color=T.TEXT_HEAD,
                      font=ctk.CTkFont(size=11),
                      command=lambda: self._open_save_template("email")).pack(side="left")
        # Item 33: a real, direct "Import HTML" entry point in Compose
        # itself (not only via Cards) -- routes straight into the existing
        # "Send as Visual HTML Card" pipeline (_enter_email_card_mode),
        # since importing external HTML is meant to preserve it, not
        # flatten it into the rich-text editor.
        self._em_import_html_btn = ctk.CTkButton(
            em_ai_row, text="📂 Import HTML", height=30, corner_radius=8,
            fg_color="transparent", hover_color=T.BG_INNER, border_width=1,
            border_color=T.BG_BORDER, text_color=T.ACCENT_TEXT,
            font=ctk.CTkFont(size=11),
            command=self._import_html_into_compose)
        self._em_import_html_btn.pack(side="left", padx=(8, 0))
        # Not disabled while already in card mode (see _apply_email_card_mode_ui) --
        # re-importing a different file while one is already active is a
        # reasonable, harmless action (it just replaces the current card),
        # unlike the rich-text toolbar/dropdowns which have nothing to act on.
        #
        # The warning message gets its OWN full-width row below the buttons
        # (P2 of the Compose reliability pass): sharing em_ai_row with three
        # buttons squeezed it to a truncated fragment hidden behind the
        # "Generate with AI" button.
        self._em_warning_var = StringVar(value="")
        self._em_warning_label = ctk.CTkLabel(
            em_left, textvariable=self._em_warning_var, text_color=T.TEXT_DIM,
            font=ctk.CTkFont(size=11), wraplength=560, justify="left", anchor="w")
        self._em_warning_label.grid(row=4, column=0, padx=16, pady=(0, 6), sticky="ew")

        self._compose_em_body = tk.Text(
            em_left, wrap="word", bg=T.resolve(T.BG_INNER), fg=T.resolve(T.TEXT_HEAD),
            insertbackground=T.resolve(T.TEXT_HEAD), font=("Segoe UI", 11),
            borderwidth=0, highlightthickness=0, relief="flat")
        # Item 10 of the Live Testing Findings pass: bold/italic are real Tk
        # tags (toggled by the toolbar above), not literal text -- this is
        # what lets the editor show genuine bold/italic instead of visible
        # <strong>/<em> tags. Known, disclosed simplification: Tk resolves a
        # font-option conflict between two tags by priority rather than
        # composing them, so a range with BOTH tags visually renders as
        # whichever has higher priority (italic wins here, "i" configured
        # after "b") -- but export to HTML (_email_rich_export_html) reads
        # the real active-tag set from the widget, not the rendered font, so
        # a combined bold+italic run still exports correctly as nested
        # <strong><em> even though the live preview only shows one style.
        self._compose_em_body.tag_configure("b", font=("Segoe UI", 11, "bold"))
        self._compose_em_body.tag_configure("i", font=("Segoe UI", 11, "italic"))
        self._compose_em_body.insert("1.0", "Dear {name},\n\nYour message here.")
        self._pillify_text_widget(self._compose_em_body)
        self._compose_em_body.grid(row=5, column=0, padx=16, pady=(0, 16), sticky="nsew")
        self._compose_em_body.bind("<KeyRelease>", lambda _e: self._update_email_warnings())
        # _em_subj_var is created once in __init__ and outlives UI rebuilds
        # (e.g. switching to/from the Warm Ivory theme), but this method runs
        # again on every rebuild — guard so the trace isn't added repeatedly.
        if not getattr(self, "_em_subj_trace_added", False):
            self._em_subj_var.trace_add("write", lambda *_a: self._update_email_warnings())
            self._em_subj_trace_added = True

        # "Send as Visual HTML Card" lock panel -- occupies the exact same
        # grid cell as _compose_em_body, swapped in/out via grid()/
        # grid_remove() (same technique already used for the sidebar's
        # preview-host/fallback swap) so the locked state can't be
        # accidentally edited through the rich-text editor underneath.
        self._em_card_lock_frame = ctk.CTkFrame(em_left, fg_color=T.BG_INNER, corner_radius=10)
        self._em_card_lock_frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            self._em_card_lock_frame, text="🔒 Visual HTML Card",
            font=ctk.CTkFont(size=14, weight="bold"), text_color=T.TEXT_HEAD,
        ).grid(row=0, column=0, padx=16, pady=(16, 4), sticky="w")
        ctk.CTkLabel(
            self._em_card_lock_frame,
            text="This message will send exactly as designed in Card Creator "
                 "(see the real rendered preview on the right) — not editable "
                 "here as rich text. To change it, edit the card in Card "
                 "Creator and click \"Insert into Compose\" again.",
            text_color=T.TEXT_MUTED, font=ctk.CTkFont(size=11),
            wraplength=420, justify="left",
        ).grid(row=1, column=0, padx=16, pady=(0, 12), sticky="w")
        ctk.CTkButton(
            self._em_card_lock_frame, text="✎ Switch to Rich Text Editing",
            fg_color=T.BG_INNER, hover_color=T.BG_BORDER, border_width=1,
            border_color=T.ACCENT, text_color=T.ACCENT_TEXT, corner_radius=6,
            height=30, font=ctk.CTkFont(size=11),
            command=self._exit_email_card_mode,
        ).grid(row=2, column=0, padx=16, pady=(0, 16), sticky="w")
        # Not grid()'d here -- only shown while _compose_card_mode is True,
        # toggled by _enter_email_card_mode/_exit_email_card_mode.

        # Email right column — SMTP status + recipients
        em_smtp_card = ctk.CTkFrame(self._em_compose_frame, fg_color=T.BG_SURFACE, corner_radius=14,
                                    border_width=1, border_color=T.BG_BORDER)
        em_smtp_card.grid(row=0, column=1, sticky="ew", pady=(0, 8))
        em_smtp_card.grid_columnconfigure(0, weight=1)

        # Item 28 (Final Premium Polish Pass): title was size=13/pady=(14,4)
        # -- every other major T.BG_SURFACE card app-wide, including this
        # exact card's own WhatsApp-side counterpart ("Preview" in
        # preview_frame above), uses size=15/pady=(16,...). Normalized so
        # this card doesn't read as a lesser tier than its siblings.
        ctk.CTkLabel(em_smtp_card, text="SMTP connection",
                     font=ctk.CTkFont(size=15, weight="bold"),
                     text_color=T.TEXT_HEAD).grid(row=0, column=0, padx=16, pady=(16, 4), sticky="w")
        self._em_smtp_status_var = StringVar(value="Not configured")
        self._em_smtp_chip = ctk.CTkLabel(
            em_smtp_card, textvariable=self._em_smtp_status_var,
            fg_color=T.BADGE_BG, corner_radius=999, padx=10, pady=4,
            # This is literally red text on BADGE_BG -- the Design System's
            # own documented DANGER_ON_BADGE case, not DANGER (3.10:1 fail).
            text_color=T.DANGER_ON_BADGE, font=ctk.CTkFont(size=11))
        self._em_smtp_chip.grid(row=0, column=1, padx=16, pady=(16, 4), sticky="e")
        self._em_validation_label = ctk.CTkLabel(
            em_smtp_card, text="", text_color=T.DANGER_ON_BADGE,
            font=ctk.CTkFont(size=11), wraplength=240, justify="left")
        self._em_validation_label.grid(row=1, column=0, columnspan=2, padx=16, pady=(0, 4), sticky="w")
        ctk.CTkButton(em_smtp_card, text="Configure in Settings →", height=30, corner_radius=6,
                      fg_color=T.BADGE_BG, hover_color=T.BG_BORDER, text_color=T.ACCENT_TEXT,
                      font=ctk.CTkFont(size=11),
                      command=lambda: self._show_view("Settings")).grid(
            row=2, column=0, columnspan=2, padx=16, pady=(0, 14), sticky="w")

        em_recip_card = ctk.CTkFrame(self._em_compose_frame, fg_color=T.BG_SURFACE, corner_radius=14,
                                     border_width=1, border_color=T.BG_BORDER)
        em_recip_card.grid(row=1, column=1, sticky="ew", pady=(0, 8))
        em_recip_card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(em_recip_card, text="Recipients",
                     font=ctk.CTkFont(size=15, weight="bold"),
                     text_color=T.TEXT_HEAD).grid(row=0, column=0, padx=16, pady=(16, 4), sticky="w")
        ctk.CTkLabel(em_recip_card, textvariable=self._em_compose_count_var,
                     text_color=T.ACCENT_TEXT, font=ctk.CTkFont(size=13, weight="bold")).grid(
            row=1, column=0, padx=16, pady=(0, 4), sticky="w")
        # P2 of the Compose reliability pass: instead of a static "sends to
        # all with an email address" line that never explained why the count
        # was lower than the contact total, this now spells out exactly who
        # is excluded and why (unsubscribed / previously bounced / no email),
        # and — after a send — what the last run actually did.
        self._em_recip_detail_var = StringVar(
            value="All contacts with an email address are included.")
        ctk.CTkLabel(em_recip_card, textvariable=self._em_recip_detail_var,
                     text_color=T.TEXT_MUTED, font=ctk.CTkFont(size=11), justify="left",
                     wraplength=300, anchor="w").grid(
            row=2, column=0, padx=16, pady=(0, 4), sticky="w")
        self._em_last_run_var = StringVar(value="")
        ctk.CTkLabel(em_recip_card, textvariable=self._em_last_run_var,
                     text_color=T.SUCCESS, font=ctk.CTkFont(size=11, weight="bold"),
                     justify="left", wraplength=300, anchor="w").grid(
            row=3, column=0, padx=16, pady=(0, 4), sticky="w")
        # Item 10 of the Live Testing Findings pass: the count used to be a
        # dead-end number -- clicking through to the actual contact list
        # (rather than just "manage contacts in the Contacts tab") answers
        # "which contacts, exactly" without leaving Compose.
        ctk.CTkButton(em_recip_card, text="View recipient list →", height=26, corner_radius=6,
                      fg_color="transparent", hover_color=T.BADGE_BG, text_color=T.ACCENT_TEXT,
                      font=ctk.CTkFont(size=11), anchor="w",
                      command=self._show_email_recipients_list).grid(
            row=4, column=0, padx=12, pady=(0, 12), sticky="w")

        em_preview_card = ctk.CTkFrame(self._em_compose_frame, fg_color=T.BG_SURFACE, corner_radius=14,
                                       border_width=1, border_color=T.BG_BORDER)
        em_preview_card.grid(row=2, column=1, sticky="nsew")
        em_preview_card.grid_columnconfigure(0, weight=1)
        em_preview_card.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(em_preview_card, text="Live preview",
                     font=ctk.CTkFont(size=15, weight="bold"),
                     text_color=T.TEXT_HEAD).grid(row=0, column=0, padx=16, pady=(16, 6), sticky="w")
        # Always-works escape hatch: renders the exact HTML that will be
        # sent (first eligible contact's data substituted) in the system
        # browser -- a real rendering engine, so it's never a blank/blurred
        # strip. Shown only in Visual HTML Card mode.
        self._em_preview_browser_btn = ctk.CTkButton(
            em_preview_card, text="↗ Open in browser", width=140, height=26, corner_radius=6,
            fg_color=T.BG_INNER, hover_color=T.BG_BORDER, border_width=1,
            border_color=T.BG_BORDER, text_color=T.ACCENT_TEXT,
            font=ctk.CTkFont(size=11),
            command=self._open_email_card_preview_in_browser)
        self._em_preview_browser_btn.grid(row=0, column=0, padx=16, pady=(14, 6), sticky="e")
        self._em_preview_browser_btn.grid_remove()
        self._em_preview_text = tk.Text(
            em_preview_card, wrap="word", bg=T.resolve(T.BG_INNER), fg=T.resolve(T.TEXT_HEAD),
            font=("Segoe UI", 11), borderwidth=0, highlightthickness=0, relief="flat",
            state="disabled")
        self._em_preview_text.tag_configure("b", font=("Segoe UI", 11, "bold"))
        self._em_preview_text.tag_configure("i", font=("Segoe UI", 11, "italic"))
        self._em_preview_text.tag_configure("muted", foreground=T.resolve(T.TEXT_MUTED))
        self._em_preview_text.grid(row=1, column=0, padx=16, pady=(0, 16), sticky="nsew")

        # Card-mode preview host: real rendered HTML (gradients/images/CTA
        # button intact), same lazy-create-on-first-use HtmlFrame pattern
        # already used by Card Creator's own Live Preview panel -- reused
        # here rather than a second, separate implementation. Occupies the
        # same cell as _em_preview_text, swapped via grid()/grid_remove().
        self._em_card_preview_host = ctk.CTkFrame(em_preview_card, fg_color=T.BG_INNER)
        self._em_card_preview_host.grid(row=1, column=0, padx=16, pady=(0, 16), sticky="nsew")
        self._em_card_preview_host.grid_remove()
        self._em_card_html_frame = None
        self._em_card_preview_fallback = ctk.CTkLabel(
            self._em_card_preview_host,
            text="Visual card preview needs the tkinterweb package, which "
                 "isn't installed. The card will still send correctly — "
                 "click \"Preview in Browser\" from Card Creator to see it.",
            text_color=T.TEXT_MUTED, font=ctk.CTkFont(size=11),
            wraplength=320, justify="left")
        if not HAS_HTML_PREVIEW:
            self._em_card_preview_fallback.pack(fill="both", expand=True, padx=12, pady=24)

        def _smtp_changed(*_):
            if not hasattr(self, "_em_smtp_chip"):
                return
            if self._em_user.get():
                self._em_smtp_status_var.set(f"{self._em_provider.get()} · {self._em_user.get()}")
                self._em_smtp_chip.configure(text_color=T.SUCCESS)
            else:
                self._em_smtp_status_var.set("Not configured")
                self._em_smtp_chip.configure(text_color=T.DANGER_ON_BADGE)

        self._em_user.trace_add("write", _smtp_changed)
        self._em_provider.trace_add("write", _smtp_changed)
        # Real bug found via live testing: _em_user/_em_provider are already
        # loaded from saved settings by the time this view is built (Compose
        # is built once at startup, after _load_settings()), so the trace
        # above never fires for that already-loaded value -- the chip stayed
        # stuck on its hardcoded "Not configured" default until something
        # else happened to re-touch those StringVars later. Sync once here
        # against whatever is actually configured right now.
        _smtp_changed()

        # ── Row 2: Shared send controls ────────────────────────────────────────
        controls = ctk.CTkFrame(frame, fg_color=T.BG_SURFACE, corner_radius=14,
                                border_width=1, border_color=T.BG_BORDER)
        controls.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        controls.grid_columnconfigure(4, weight=1)

        ctk.CTkButton(controls, text="Start", width=90,
                      fg_color=T.ACCENT, hover_color=T.ACCENT_HOVER,
                      text_color=T.TEXT_HEAD,
                      corner_radius=8, font=ctk.CTkFont(size=13, weight="bold"),
                      command=self._dispatch_send).grid(
            row=0, column=0, padx=(16, 8), pady=(14, 8))
        # "Send test to myself" — builds and sends ONE message exactly as a
        # real batch would (same template, same _build_email_message, same
        # compliance footer), to the configured SMTP account, so a campaign
        # can be verified in a real inbox before it goes to real recipients.
        # Email-only (hidden on the WhatsApp channel); never logs a campaign
        # row and never counts toward the warm-up ramp.
        self._em_test_send_btn = ctk.CTkButton(
            controls, text="✉ Send test to myself", width=150,
            fg_color=T.BG_INNER, hover_color=T.BG_BORDER,
            border_width=1, border_color=T.ACCENT,
            text_color=T.ACCENT_TEXT, corner_radius=8,
            font=ctk.CTkFont(size=12),
            command=self._send_test_email_to_self)
        self._em_test_send_btn.grid(row=0, column=1, padx=8, pady=(14, 8))
        # Compose opens on the WhatsApp channel by default — this is
        # Email-only, shown by _on_channel_switch("Email").
        self._em_test_send_btn.grid_remove()
        # Item 27 (Final Premium Polish Pass): was fg_color="transparent" on
        # this T.BG_SURFACE card -- ACCENT text measured 2.16:1 in Dark mode,
        # a real WCAG fail (well under even the 3:1 UI-component floor), and
        # hover_color=T.BG_SURFACE was a no-op (identical to the card behind
        # it). Matches History's own "Duplicate" button fix (Item 12): a real
        # T.BG_INNER fill gives 3.2:1 (accepted) and makes hover meaningful.
        self._compose_pause_btn = ctk.CTkButton(
            controls, text="Pause / Resume", width=120,
            fg_color=T.BG_INNER, hover_color=T.BG_BORDER,
            border_width=1, border_color=T.ACCENT,
            text_color=T.ACCENT_TEXT, corner_radius=8,
            command=self._toggle_pause)
        self._compose_pause_btn.grid(row=0, column=2, padx=8, pady=(14, 8))
        ctk.CTkButton(controls, text="Stop", width=80,
                      fg_color=T.DANGER, hover_color=T.DANGER_HOVER,
                      text_color=T.TEXT_HEAD,
                      corner_radius=8, command=self._dispatch_stop).grid(
            row=0, column=3, padx=8, pady=(14, 8))

        # ── Rate limit — editable right here, not just in Settings ─────────────
        rate_row = ctk.CTkFrame(controls, fg_color="transparent")
        rate_row.grid(row=1, column=0, columnspan=4, padx=16, pady=(0, 8), sticky="ew")
        rate_row.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(rate_row, text="Delay between sends", text_color=T.TEXT_MUTED,
                     font=ctk.CTkFont(size=11)).grid(row=0, column=0, padx=(0, 10), sticky="w")
        self._compose_delay_slider = ctk.CTkSlider(
            rate_row, from_=10, to=120, number_of_steps=110,
            command=self._on_compose_delay_change, progress_color=T.ACCENT)
        self._compose_delay_slider.set(self.delay_var.get())
        self._compose_delay_slider.grid(row=0, column=1, sticky="ew", padx=(0, 10))
        self._compose_delay_label = ctk.CTkLabel(rate_row, text=f"{self.delay_var.get()} sec",
                                                  text_color=T.TEXT_HEAD, width=50)
        self._compose_delay_label.grid(row=0, column=2, sticky="e")
        self._send_rate_warning_var = StringVar(value="")
        ctk.CTkLabel(rate_row, textvariable=self._send_rate_warning_var, text_color=T.DANGER_ON_BADGE,
                     font=ctk.CTkFont(size=10)).grid(row=1, column=0, columnspan=3, sticky="w", pady=(2, 0))

        prog_row = ctk.CTkFrame(controls, fg_color="transparent")
        prog_row.grid(row=2, column=0, columnspan=4, padx=16, pady=(0, 12), sticky="ew")
        prog_row.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(prog_row, textvariable=self.progress_status_var,
                     text_color=T.TEXT_MUTED, font=ctk.CTkFont(size=11), anchor="w").grid(
            row=0, column=0, sticky="w")
        self.compose_progress = ctk.CTkProgressBar(prog_row, height=8, corner_radius=4,
                                                    progress_color=T.ACCENT, fg_color=T.BG_SURFACE)
        self.compose_progress.grid(row=1, column=0, sticky="ew", pady=(4, 0))
        self.compose_progress.set(0)
        self._update_send_rate_warning()
        # A view rebuild (e.g. entering/leaving Warm Ivory) constructs fresh
        # widgets every time -- re-apply whatever card-mode state was
        # already active so it isn't silently lost/reset by the rebuild.
        self._apply_email_card_mode_ui()
        if self._compose_card_mode:
            self._render_email_card_preview()

    def _on_channel_switch(self, channel: str) -> None:
        if channel == "WhatsApp":
            self._wa_compose_frame.grid()
            self._em_compose_frame.grid_remove()
            self._compose_pause_btn.configure(state="normal")
            if hasattr(self, "_em_test_send_btn"):
                self._em_test_send_btn.grid_remove()
        else:
            self._wa_compose_frame.grid_remove()
            self._em_compose_frame.grid()
            self._compose_pause_btn.configure(state="normal")
            if hasattr(self, "_em_test_send_btn"):
                self._em_test_send_btn.grid()
            self._refresh_compose_email_recipients()
            if self._compose_card_mode:
                self._render_email_card_preview()
            else:
                self._refresh_email_preview()

    def _dispatch_send(self) -> None:
        if self._compose_channel_var.get() == "Email":
            self._start_email_from_compose()
        else:
            self._start_sending()

    def _dispatch_stop(self) -> None:
        if self._compose_channel_var.get() == "Email":
            self._em_stop_flag.set()
            self.progress_status_var.set("Stopping…")
        else:
            self._stop_sending()

    def _email_recipient_breakdown(self) -> dict:
        """Who the next email send will actually reach, and who it won't.
        `eligible` is the real recipient list (has an email, not
        unsubscribed, not previously bounced); `warmup_cap` is how many of
        those can go out today under the warm-up ramp (None = no cap
        applies)."""
        with_email = [c for c in self.contacts if c.email]
        eligible = [c for c in with_email if not c.opted_out and not c.bounced]
        warmup_cap = None
        if getattr(self, "email_warmup_enabled_var", None) is not None and \
                self.email_warmup_enabled_var.get():
            try:
                remaining = self._email_warmup_remaining_today()
                if remaining < len(eligible):
                    warmup_cap = remaining
            except Exception:
                warmup_cap = None
        return {
            "eligible": eligible,
            "unsubscribed": sum(1 for c in with_email if c.opted_out),
            "bounced": sum(1 for c in with_email if c.bounced),
            "no_email": len(self.contacts) - len(with_email),
            "warmup_cap": warmup_cap,
        }

    def _refresh_compose_email_recipients(self) -> None:
        if not hasattr(self, "_em_compose_count_var"):
            return
        b = self._email_recipient_breakdown()
        n = len(b["eligible"])
        self._em_compose_count_var.set(
            f"{n} will receive this send" if n != 1 else "1 will receive this send")
        if hasattr(self, "_em_recip_detail_var"):
            excl = []
            if b["unsubscribed"]:
                excl.append(f"{b['unsubscribed']} unsubscribed")
            if b["bounced"]:
                excl.append(f"{b['bounced']} previously bounced")
            if b["no_email"]:
                excl.append(f"{b['no_email']} with no email address")
            if excl:
                detail = "Excluded: " + ", ".join(excl) + "."
            else:
                detail = "All contacts with an email address are included."
            if b["warmup_cap"] is not None:
                detail += (f"\n⏳ Warm-up mode: only {b['warmup_cap']} can be sent today "
                           f"(of {n} eligible). Turn off in Settings → Campaign Safety "
                           "for an established account.")
            self._em_recip_detail_var.set(detail)

    def _start_email_from_compose(self) -> None:
        if self._em_send_thread and self._em_send_thread.is_alive():
            messagebox.showinfo("Campaign Running", "An email campaign is already in progress.")
            return

        contacts = [c for c in self.contacts if c.email and not c.opted_out and not c.bounced]
        if not contacts:
            self.progress_status_var.set(
                "⚠ No contacts with email. Import contacts in the Contacts tab first.")
            return
        if not self._em_user.get() or not self._em_pass.get():
            self.progress_status_var.set(
                "⚠ SMTP not configured. Add credentials in Settings → Email.")
            if hasattr(self, "_em_validation_label"):
                self._em_validation_label.configure(
                    text="Configure SMTP in Settings before sending.")
            return

        if self.email_warmup_enabled_var.get():
            remaining_today = self._email_warmup_remaining_today()
            if len(contacts) > remaining_today:
                messagebox.showwarning(
                    "Warm-Up Limit",
                    f"Warm-up mode allows {remaining_today} more email(s) today "
                    f"({warmup_scheduler.ramp_status_text(warmup_scheduler.parse_date(self._email_warmup_start_date), date.today(), self.daily_limit_var.get())}). "
                    "Reduce your recipient list, wait until tomorrow, or turn off warm-up mode "
                    "in Settings → Campaign Safety if this account is already established.")
                return

        if hasattr(self, "_em_validation_label"):
            self._em_validation_label.configure(text="")
        # Single source of truth for what actually gets sent (Visual HTML
        # Card HTML in card mode, else the rich-text editor's real HTML
        # export) -- shared with "Send test to myself" so they can't diverge.
        html_template, plain_template = self._current_email_templates()
        if not plain_template.strip():
            self.progress_status_var.set("⚠ Email body is empty.")
            return
        subject_template = self._em_subj_var.get()

        def sub(text, m):
            for k, v in m.items():
                text = text.replace(f"{{{k}}}", str(v))
            return text

        recipients = []
        preview_lines = []
        for contact in contacts:
            vars_map = {
                "name": contact.name, "email": contact.email,
                "phone": contact.phone, "sender": self._em_from_name.get(),
            }
            vars_map.update(contact.custom_fields)
            subject = sub(subject_template, vars_map)
            recipients.append((contact, subject, sub(html_template, vars_map),
                               sub(plain_template, vars_map)))
            if len(preview_lines) < 3:
                preview_lines.append(
                    f"To: {contact.name or contact.email}\nSubject: {subject}\n"
                    f"{sub(plain_template, vars_map)}")

        from .send_dialogs import show_send_confirmation
        from ..core.contact_quality import flag_low_quality_emails
        quality_flags = flag_low_quality_emails(c.email for c, *_rest in recipients)

        b = self._email_recipient_breakdown()
        excl_bits = []
        if b["unsubscribed"]:
            excl_bits.append(f"{b['unsubscribed']} unsubscribed")
        if b["bounced"]:
            excl_bits.append(f"{b['bounced']} previously bounced")
        if b["no_email"]:
            excl_bits.append(f"{b['no_email']} with no email address")
        exclusions_note = ""
        if excl_bits:
            exclusions_note = (
                f"{len(self.contacts)} contacts total · excluded from this send: "
                + ", ".join(excl_bits) + ".")

        show_send_confirmation(
            self, "email", len(recipients), float(self._em_delay.get() or 5), preview_lines,
            on_confirm=lambda: self._execute_email_send(recipients),
            subject=recipients[0][1] if recipients else subject_template,
            quality_flag_count=len(quality_flags),
            exclusions_note=exclusions_note)

    def _send_test_email_to_self(self) -> None:
        """Send ONE message — built exactly as a real batch would be
        (same template selection, same _build_email_message,
        same compliance footer) — to the configured SMTP account, so a
        campaign can be verified in a real inbox before it reaches real
        recipients. Deliberately does NOT create a campaign row, write to
        message_logs, or count against the warm-up ramp: it's a preview,
        not a send to the audience."""
        if not self._em_user.get() or not self._em_pass.get():
            self.progress_status_var.set(
                "⚠ SMTP not configured — add credentials in Settings → Email first.")
            return
        html_template, plain_template = self._current_email_templates()
        if not (plain_template or "").strip():
            self.progress_status_var.set("⚠ Nothing to test — the email body is empty.")
            return

        # Use the first eligible real contact's data so the test shows real
        # substitution; fall back to obvious sample values if there are none.
        eligible = [c for c in self.contacts
                    if c.email and not c.opted_out and not c.bounced]
        if eligible:
            c = eligible[0]
            vars_map = {"name": c.name, "email": c.email, "phone": c.phone,
                        "sender": self._em_from_name.get()}
            vars_map.update(c.custom_fields)
        else:
            vars_map = {"name": "Sample Name", "email": self._em_user.get(),
                        "phone": "+10000000000", "sender": self._em_from_name.get()}

        def sub(text: str) -> str:
            for k, v in vars_map.items():
                text = text.replace(f"{{{k}}}", str(v))
            return text

        to_addr = self._em_user.get().strip()
        subject = "[TEST] " + sub(self._em_subj_var.get())
        html_body = sub(html_template)
        plain_body = sub(plain_template)

        btn = getattr(self, "_em_test_send_btn", None)
        if btn is not None:
            btn.configure(state="disabled", text="Sending test…")
        self.progress_status_var.set(f"Sending test message to {to_addr}…")

        def worker():
            try:
                ctx = ssl.create_default_context()
                conn = smtplib.SMTP(self._em_host.get(),
                                    int(self._em_port.get() or 587), timeout=15)
                conn.starttls(context=ctx)
                conn.login(self._em_user.get(), self._em_pass.get())
                msg = self._build_email_message(subject, to_addr, html_body, plain_body)
                conn.sendmail(self._em_from_addr.get(), to_addr, msg.as_string())
                try:
                    conn.quit()
                except Exception:
                    pass
                ok, detail = True, to_addr
            except Exception as ex:
                ok, detail = False, str(ex)

            def done():
                if btn is not None:
                    btn.configure(state="normal", text="✉ Send test to myself")
                if ok:
                    self.progress_status_var.set(
                        f"✅ Test sent to {detail} — open it in your inbox to verify styling.")
                    show_toast(self, f"Test email sent to {detail}.", kind="success")
                else:
                    self.progress_status_var.set(f"⚠ Test send failed: {detail}")
            self.after(0, done)

        threading.Thread(target=worker, daemon=True).start()

    def _execute_email_send(self, recipients: list) -> None:
        """Real send for a specific list of (contact, subject, html_body[, plain_body])
        tuples — used both for the initial campaign and Retry Failed Only."""
        self._em_stop_flag.clear()
        self._em_pause_event.set()
        self.compose_progress.set(0)
        self.progress_status_var.set("Connecting to SMTP…")
        campaign_name = f"Email {datetime.now().strftime('%Y-%m-%d %H:%M')}"

        def worker():
            def progress(sent, failed, total, to_addr):
                def _upd():
                    self.progress_status_var.set(
                        f"{sent} sent · {failed} failed — {to_addr} ({sent + failed}/{total})")
                    self.compose_progress.set((sent + failed) / total if total else 0)
                self.after(0, _upd)

            try:
                result = self._send_email_campaign(
                    recipients, campaign_name, progress_callback=progress,
                    stop_flag=self._em_stop_flag, pause_event=self._em_pause_event)
            except Exception as ex:
                # Computed here, not inside the deferred lambda -- `ex` is
                # auto-deleted by Python at except-block exit, before
                # self.after()'s callback runs; an f-string referencing `ex`
                # there raises a NameError that Tk's default handler silently
                # swallows (stderr only), leaving progress_status_var
                # unchanged instead of showing the real SMTP error.
                error_message = str(ex)
                self.after(0, lambda: self.progress_status_var.set(f"⚠ SMTP error: {error_message}"))
                return

            def finish():
                self.compose_progress.set(1)
                self.progress_status_var.set(
                    f"Done — ✅ {result['sent']} sent  ❌ {result['failed']} failed")
                if hasattr(self, "_em_last_run_var"):
                    ts = datetime.now().strftime("%H:%M")
                    self._em_last_run_var.set(
                        f"Last run ({ts}): {result['sent']} sent, {result['failed']} failed "
                        "(SMTP-accepted, not confirmed delivered).")
                self._refresh_compose_email_recipients()
                if result.get("sent", 0) > 0:
                    self._ensure_email_warmup_started()
                    self._update_email_warmup_status_label()
                    # Real bounces (address doesn't exist, blocked, etc.)
                    # come back as a separate message to the sending
                    # inbox on their own schedule -- this campaign's own
                    # Sent count only ever meant "SMTP accepted it," never
                    # "delivered." One automatic, silent reconciliation
                    # pass a few minutes later closes most of that gap for
                    # fast hard-bounces; "Check for Bounces" in the report
                    # dialog/History covers anything slower.
                    self.after(BOUNCE_AUTO_CHECK_DELAY_MS,
                               lambda cid=result.get("campaign_id"):
                                   self._check_campaign_for_bounces(cid, silent=True))
                self._show_email_report(result, campaign_name)

            self.after(0, finish)

        self._em_send_thread = threading.Thread(target=worker, daemon=True)
        self._em_send_thread.start()

    def _show_email_report(self, result: dict, campaign_name: str = "Email Campaign") -> None:
        from .send_dialogs import show_send_report
        failed_details = [(c.name or c.email, reason)
                          for c, _s, _b, _p, reason in result.get("failed_items", [])]
        failed_recipients = [(c, s, b, p) for c, s, b, p, _r in result.get("failed_items", [])]

        def retry_failed() -> None:
            self._execute_email_send(failed_recipients)

        def export_csv() -> None:
            path = filedialog.asksaveasfilename(
                title="Export Email Report", defaultextension=".csv",
                filetypes=[("CSV files", "*.csv")], initialfile="email_campaign_report.csv")
            if not path:
                return
            import csv as csv_module
            with open(path, "w", newline="", encoding="utf-8-sig") as handle:
                writer = csv_module.writer(handle)
                writer.writerow(["contact", "email", "status", "reason"])
                for label, reason in failed_details:
                    writer.writerow([label, "", "failed", reason])
                writer.writerow([f"{result['sent']} sent total", "", "sent", ""])
            show_toast(self, f"Report exported to {os.path.basename(path)}", kind="success")

        campaign_id = result.get("campaign_id")
        initial_bounced = (self.db.get_campaign_bounce_stats(campaign_id)["bounced_count"]
                            if campaign_id else 0)

        def check_bounces(dialog_callback) -> None:
            def on_done(check_result) -> None:
                if check_result is None:
                    dialog_callback(False, 0, "No campaign to check.")
                    return
                if not check_result.ok:
                    dialog_callback(False, 0, check_result.error)
                    return
                bounced_count = (self.db.get_campaign_bounce_stats(campaign_id)["bounced_count"]
                                  if campaign_id else 0)
                dialog_callback(True, bounced_count, "")
            self._check_campaign_for_bounces(campaign_id, silent=False, on_done=on_done)

        def ai_summary(dialog_callback) -> None:
            self._request_ai_campaign_summary(
                campaign_name=campaign_name, sent=result.get("sent", 0),
                failed=result.get("failed", 0), bounced=initial_bounced,
                dialog_callback=dialog_callback)

        show_send_report(
            self, "email", result.get("sent", 0), result.get("failed", 0), failed_details,
            on_retry_failed=retry_failed if failed_recipients else None,
            on_export=export_csv,
            on_check_bounces=check_bounces if campaign_id else None,
            bounced=initial_bounced,
            on_ai_summary=ai_summary,
        )

    def _request_ai_campaign_summary(self, campaign_name: str, sent: int, failed: int,
                                      bounced: int, dialog_callback) -> None:
        """Item 34 (sub-item 5): a plain-language AI summary of one real,
        already-completed campaign, grounded entirely in this campaign's own
        real sent/failed/bounced counts (already shown in the report dialog
        above) -- never invented numbers. Runs off the UI thread, same
        pattern as every other AI call in this app (e.g. _test_ai_key)."""
        api_key = self._ai_api_key.get()
        if not api_key:
            dialog_callback(False, "", "Add an AI API key in Settings first.")
            return
        provider = self._ai_provider.get()
        stats = {
            "campaign_name": campaign_name, "total_sent": sent,
            "failed": failed, "bounced": bounced,
            "bounce_check_status": (
                f"{bounced} bounce(s) confirmed so far; more may still arrive"
                if bounced else
                "no bounces reported yet — an automatic re-check runs a few minutes "
                "after sending, and \"Check for Bounces\" can be run any time"),
        }

        def worker():
            try:
                summary = ai_service.summarize_campaign_performance(stats, api_key, provider=provider)
            except AIServiceError as ex:
                message = str(ex)
                self.after(0, lambda: dialog_callback(False, "", message))
                return
            self.after(0, lambda: dialog_callback(True, summary, ""))

        threading.Thread(target=worker, daemon=True).start()

    def _check_campaign_for_bounces(self, campaign_id: Optional[int], silent: bool = False,
                                     on_done=None) -> None:
        """Real IMAP bounce/NDR reconciliation for one campaign: reads the
        sending account's own inbox (read-only) for real bounce messages and
        cross-references them against the exact set of addresses this
        campaign actually sent to (SMTP-accepted, i.e. status='sent' and
        not yet reconciled). Any confirmed bounce updates message_logs
        (bounced/bounce_reason) and the matching contact's own bounced flag,
        so future campaigns don't keep sending to a dead address.

        Runs entirely in a background thread; never blocks the UI, never
        raises into it -- matches this app's own established pattern for
        every other background network call (update checks, AI calls,
        SMTP test). `silent=True` (the automatic post-send check) only logs
        + updates data on success and stays quiet on a soft failure (no
        IMAP settings guessable, offline, etc.) rather than popping a toast
        for something the user didn't explicitly ask for; a manual "Check
        for Bounces" click (silent=False) always shows a real result."""
        if not campaign_id:
            if on_done:
                on_done(None)
            return

        logs = self.db.get_sent_email_logs_for_bounce_check(campaign_id)
        candidate_emails = {log.contact_email for log in logs if log.contact_email}
        if not candidate_emails:
            if not silent:
                show_toast(self, "Nothing to check — no un-reconciled sent emails "
                                  "for this campaign.", kind="info")
            if on_done:
                on_done(bounce_checker.BounceCheckResult(ok=True, bounces={}))
            return

        imap_target = bounce_checker.guess_imap_host(self._em_host.get(), self._em_provider.get())
        if imap_target is None:
            message = ("Can't auto-detect IMAP settings for this email provider — "
                       "bounce checking isn't available for a custom SMTP host yet.")
            if not silent:
                show_toast(self, message, kind="error")
            self._log_activity(f"Bounce check skipped for campaign {campaign_id}: {message}")
            if on_done:
                on_done(bounce_checker.BounceCheckResult(ok=False, error=message))
            return
        imap_host, imap_port = imap_target
        username = self._em_user.get()
        password = self._em_pass.get()

        def worker():
            result = bounce_checker.check_for_bounces(
                imap_host, imap_port, username, password, candidate_emails)

            def finish():
                if not result.ok:
                    if not silent:
                        show_toast(self, f"Bounce check failed: {result.error}", kind="error")
                    self._log_activity(f"Bounce check failed for campaign {campaign_id}: {result.error}")
                    if on_done:
                        on_done(result)
                    return

                newly_marked = 0
                for log in logs:
                    addr = (log.contact_email or "").strip().lower()
                    if addr in result.bounces and not log.bounced:
                        reason = result.bounces[addr]
                        if self.db.mark_message_log_bounced(log.id, reason):
                            newly_marked += 1
                            self.db.set_contact_bounced_by_email(log.contact_email, True)
                            for contact in self.contacts:
                                if contact.email and contact.email.strip().lower() == addr:
                                    contact.bounced = True

                if newly_marked:
                    self._log_activity(
                        f"Bounce check: {newly_marked} confirmed bounce(s) found "
                        f"for campaign {campaign_id}.")
                    if not silent:
                        show_toast(self, f"{newly_marked} bounce(s) confirmed and reconciled.",
                                   kind="success")
                    if hasattr(self, "_history_scroll"):
                        self._history_campaigns = self.db.get_recent_campaigns_summary(limit=100)
                        self._render_history_rows(self._header_search_var.get()
                                                   if hasattr(self, "_header_search_var") else "")
                    if getattr(self, "_contacts_directory_rendered", False):
                        self._render_contacts_directory()
                    if hasattr(self, "compose_contacts_frame"):
                        self._render_compose_contacts()
                elif not silent:
                    show_toast(self, "Checked — no new bounces found.", kind="success")

                if on_done:
                    on_done(result)

            self.after(0, finish)

        threading.Thread(target=worker, daemon=True).start()

    def _current_email_templates(self) -> tuple:
        """The single source of truth for "what will actually be sent" from
        the Compose Email panel: returns (html_template, plain_template) for
        the current mode — the real Visual HTML Card HTML when a card is
        loaded (Card Creator's Insert-into-Compose / Import HTML), otherwise
        the rich-text editor's real HTML export. Shared by
        _start_email_from_compose and _send_test_email_to_self so a test send
        and a real batch can never diverge on which body they use."""
        if self._compose_card_mode and self._compose_card_html_template:
            html_template = self._compose_card_html_template
            plain_template = self._strip_html_for_preview(html_template)
        else:
            html_template = self._email_rich_export_html(self._compose_em_body) if hasattr(
                self, "_compose_em_body") else ""
            plain_template = self._get_text_with_tokens(self._compose_em_body) if hasattr(
                self, "_compose_em_body") else ""
        return html_template, plain_template

    def _build_email_message(self, subject: str, to_addr: str, html_body: str,
                             plain_body: str = "") -> MIMEMultipart:
        """Build the real outgoing message: a proper multipart/alternative
        carrying BOTH a text/plain part (accessibility + a real deliverability
        signal — a bare HTML-only body scores worse with spam filters) and the
        full text/html part with every inline style intact and unmodified
        except the compliance footer. The HTML is NEVER flattened here — what
        Card Creator / Import HTML produced is exactly what goes on the wire.

        `plain_body` is the caller's own plain-text template when it has one;
        otherwise a readable text rendering is derived from the HTML so the
        text/plain part is never empty."""
        html_body = self._add_unsubscribe_footer(html_body)
        if not (plain_body or "").strip():
            plain_body = self._strip_html_for_preview(html_body)
        if "reply" not in plain_body.lower() or "stop" not in plain_body.lower():
            plain_body = (plain_body.rstrip()
                          + "\n\n---\nDon't want these emails? Reply STOP to unsubscribe.")
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{self._em_from_name.get()} <{self._em_from_addr.get()}>"
        msg["To"] = to_addr
        # RFC 2046 §5.1.4: least-rich alternative first, richest last — a
        # client picks the last part it can render.
        msg.attach(MIMEText(plain_body, "plain", "utf-8"))
        msg.attach(MIMEText(html_body, "html", "utf-8"))
        return msg

    def _add_unsubscribe_footer(self, html_body: str) -> str:
        """Append a compliance footer to every outgoing email, no exceptions
        — this is what keeps the sending domain's reputation safe at high
        volume (CAN-SPAM/GDPR expectation). Always appended regardless of
        what the user's own template contains, rather than trying to detect
        an existing unsubscribe mention, since a fragile heuristic here is
        worse than an occasional harmless duplicate footer."""
        sender_name = self._em_from_name.get() or "this sender"
        sender_email = self._em_from_addr.get() or ""
        footer = (
            '<hr style="border:none;border-top:1px solid #ddd;margin:24px 0 12px 0">'
            '<p style="font-size:11px;color:#999;text-align:center;font-family:sans-serif">'
            f"You're receiving this email from {sender_name}"
            f"{' (' + sender_email + ')' if sender_email else ''}.<br>"
            "Don't want these emails? Reply <b>STOP</b> to unsubscribe."
            "</p>"
        )
        lower = html_body.lower()
        idx = lower.rfind("</body>")
        if idx != -1:
            return html_body[:idx] + footer + html_body[idx:]
        return html_body + footer

    def _send_email_campaign(self, recipients, campaign_name: str,
                              progress_callback=None, stop_flag=None, pause_event=None) -> dict:
        """Send pre-resolved recipient tuples over SMTP, logging each to
        message_logs. Accepts the Compose 4-tuple
        (contact, subject, html_body, plain_body) and the AI-Cards 3-tuple
        (contact, subject, html_body) — the text/plain alternative is derived
        from the HTML when no plain_body is supplied. Shared by Compose and
        AI Cards sends.

        Returns {"sent": int, "failed": int, "campaign_id": Optional[int],
        "failed_items": [(contact, subject, html_body, plain_body, reason), ...]}.
        """
        total = len(recipients)
        ctx = ssl.create_default_context()
        conn = smtplib.SMTP(self._em_host.get(), int(self._em_port.get() or 587), timeout=10)
        conn.starttls(context=ctx)
        conn.login(self._em_user.get(), self._em_pass.get())

        db = DatabaseManager()
        campaign_record = Campaign(
            name=campaign_name,
            message_template="",
            total_contacts=total,
            message_delay=int(float(self._em_delay.get() or 5)),
            use_jitter=False,
        )
        campaign_id = db.add_campaign(campaign_record)
        sent = 0
        failed_items = []

        for row in recipients:
            # Accept both the Compose 4-tuple (contact, subject, html, plain)
            # and the AI-Cards 3-tuple (contact, subject, html) — the plain
            # part is derived from the HTML when the caller didn't supply one.
            contact, subject, html_body = row[0], row[1], row[2]
            plain_body = row[3] if len(row) > 3 else ""
            if stop_flag is not None and stop_flag.is_set():
                break
            if pause_event is not None:
                pause_event.wait()
            to_addr = (contact.email or "").strip()
            msg = self._build_email_message(subject, to_addr, html_body, plain_body)
            # message_text is logged as the real HTML that went on the wire
            # (footer included) — read back verbatim by the bounce checker
            # and the report/export.
            logged_html = self._add_unsubscribe_footer(html_body)
            try:
                conn.sendmail(self._em_from_addr.get(), to_addr, msg.as_string())
                sent += 1
                db.add_message_log(MessageLog(
                    campaign_id=campaign_id, contact_email=to_addr,
                    contact_name=contact.name, subject=subject,
                    message_text=logged_html, status=MessageStatus.SENT,
                    sent_at=datetime.now(),
                ))
                if progress_callback:
                    progress_callback(sent, len(failed_items), total, to_addr)
            except Exception as ex:
                failed_items.append((contact, subject, html_body, plain_body, str(ex)))
                db.add_message_log(MessageLog(
                    campaign_id=campaign_id, contact_email=to_addr,
                    contact_name=contact.name, subject=subject,
                    message_text=html_body, status=MessageStatus.FAILED,
                    error_message=str(ex),
                ))
                if progress_callback:
                    progress_callback(sent, len(failed_items), total, to_addr)

            base_delay = float(self._em_delay.get() or 5)
            if self.jitter_var.get():
                delay = max(1.0, base_delay + random.randint(-JITTER_RANGE, JITTER_RANGE))
            else:
                delay = base_delay
            time.sleep(delay)

        try:
            conn.quit()
        except Exception:
            pass

        if campaign_id:
            db.update_campaign(campaign_id, sent, total - sent)

        return {"sent": sent, "failed": len(failed_items), "campaign_id": campaign_id,
                 "failed_items": failed_items}

    def _test_smtp_connection(self, on_result=None) -> None:
        """Real SMTP connect+login test against the current _em_* fields.

        on_result(success: bool, message: str), called on the main thread.
        Defaults to the Settings page's own messagebox popups when omitted —
        callers like the setup wizard pass their own inline-status callback.
        """
        def default_result(success: bool, message: str) -> None:
            if success:
                messagebox.showinfo("SMTP test", message)
            else:
                messagebox.showerror("Connection failed", message)

        callback = on_result or default_result

        def worker():
            try:
                conn = smtplib.SMTP(
                    self._em_host.get(), int(self._em_port.get()), timeout=10)
                conn.starttls(context=ssl.create_default_context())
                conn.login(self._em_user.get(), self._em_pass.get())
                conn.quit()
                self.after(0, lambda: callback(True, "Connection successful ✅"))
            except smtplib.SMTPAuthenticationError:
                self.after(0, lambda: callback(
                    False, "Wrong username/password.\nFor Gmail use an App Password."))
            except Exception as ex:
                # Computed here, not inside the deferred lambda -- see the
                # SMTP-error fix above in this same file for why.
                error_message = str(ex)
                self.after(0, lambda: callback(False, error_message))

        threading.Thread(target=worker, daemon=True).start()

    def _build_reports_view(self) -> None:
        frame = self._new_view_frame("Reports")
        frame.grid_rowconfigure(3, weight=1)
        frame.grid_columnconfigure(0, weight=1)

        hero = ctk.CTkFrame(frame, fg_color=T.BG_SURFACE, corner_radius=14,
                            border_width=1, border_color=T.BG_BORDER)
        hero.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        hero.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(hero, text="Reports & Analytics",
                     font=ctk.CTkFont(size=15, weight="bold"),
                     text_color=T.TEXT_HEAD).grid(
            row=0, column=0, padx=16, pady=(14, 4), sticky="w")
        ctk.CTkLabel(hero, textvariable=self.reports_feed_var,
                     text_color=T.TEXT_MUTED, font=ctk.CTkFont(size=12)).grid(
            row=1, column=0, padx=16, pady=(0, 14), sticky="w")
        ctk.CTkLabel(hero, text="Live Monitoring", fg_color=T.BADGE_BG,
                     corner_radius=999, padx=12, pady=6,
                     text_color=T.ACCENT_TEXT, font=ctk.CTkFont(size=11, weight="bold"),
                     ).grid(row=0, column=1, rowspan=2, padx=16, pady=14, sticky="e")

        stats_strip = ctk.CTkFrame(frame, fg_color=T.BG_SURFACE, corner_radius=14,
                                   border_width=1, border_color=T.BG_BORDER)
        stats_strip.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        stat_fg_colors = [T.ACCENT, T.SUCCESS, T.ACCENT, T.DANGER]
        blocks = [
            ("Sent",      self.sent_count_var),
            ("Delivered", self.delivered_count_var),
            ("Read",      self.read_count_var),
            ("Failed",    self.failed_count_var),
        ]
        for index, ((title, variable), fg) in enumerate(zip(blocks, stat_fg_colors)):
            stats_strip.grid_columnconfigure(index, weight=1)
            block = ctk.CTkFrame(stats_strip, fg_color=T.BADGE_BG, corner_radius=12)
            block.grid(row=0, column=index, padx=8, pady=10, sticky="nsew")
            ctk.CTkLabel(block, text=title, text_color=T.TEXT_MUTED,
                         font=ctk.CTkFont(size=12)).pack(anchor="w", padx=14, pady=(12, 2))
            ctk.CTkLabel(block, textvariable=variable,
                         font=ctk.CTkFont(size=24, weight="bold"),
                         text_color=fg).pack(anchor="w", padx=14, pady=(0, 4))
            ctk.CTkLabel(block, text="Live", fg_color=T.BG_INNER,
                         corner_radius=999, padx=8, pady=3,
                         text_color=fg, font=ctk.CTkFont(size=10, weight="bold"),
                         ).pack(anchor="w", padx=14, pady=(0, 12))

        rate_frame = ctk.CTkFrame(frame, fg_color=T.BG_SURFACE, corner_radius=14,
                                  border_width=1, border_color=T.BG_BORDER)
        rate_frame.grid(row=2, column=0, sticky="ew", pady=(0, 12))
        rate_frame.grid_columnconfigure(1, weight=1)
        # Item 28 (Final Premium Polish Pass): every other major T.BG_SURFACE
        # card's title app-wide uses size=15 -- this one was the sole size=14
        # outlier. pady=14 (matching this row's other 3 elements) is
        # deliberately left as-is: this card is a genuinely different,
        # single-row layout (title/progress-bar/rate all on one row), not
        # the title-block layout the size=15/pady=(16,...) convention
        # otherwise implies, so only the font size needed normalizing.
        ctk.CTkLabel(rate_frame, text="Delivery Rate",
                     font=ctk.CTkFont(size=15, weight="bold"),
                     text_color=T.TEXT_HEAD).grid(
            row=0, column=0, padx=16, pady=14, sticky="w")
        ctk.CTkLabel(rate_frame, text="Analytics Stream", fg_color=T.BADGE_BG,
                     corner_radius=999, padx=10, pady=5,
                     text_color=T.ACCENT_TEXT, font=ctk.CTkFont(size=11),
                     ).grid(row=0, column=2, padx=(0, 10), pady=14, sticky="e")
        self.delivery_progress = ctk.CTkProgressBar(rate_frame, corner_radius=4)
        self.delivery_progress.grid(row=0, column=1, padx=10, pady=14, sticky="ew")
        self.delivery_progress.set(0)
        self.delivery_progress.configure(progress_color=T.ACCENT)
        ctk.CTkLabel(rate_frame, textvariable=self.delivery_rate_var,
                     text_color=T.TEXT_HEAD).grid(row=0, column=3, padx=14, pady=14, sticky="e")

        body = ctk.CTkFrame(frame, fg_color=T.BG_SURFACE, corner_radius=14,
                            border_width=1, border_color=T.BG_BORDER)
        body.grid(row=3, column=0, sticky="nsew")
        body.grid_rowconfigure(4, weight=1)
        body.grid_columnconfigure(0, weight=1)

        actions = ctk.CTkFrame(body, fg_color="transparent")
        actions.grid(row=0, column=0, sticky="ew", padx=14, pady=(14, 8))
        actions.grid_columnconfigure(5, weight=1)
        ctk.CTkLabel(actions, text="Period", text_color=T.TEXT_HEAD).grid(
            row=0, column=0, padx=(0, 8), pady=8)
        self.report_period_menu = ctk.CTkOptionMenu(
            actions,
            values=["today", "week", "month", "all"],
            variable=self.report_period_var,
            command=lambda _value: self._refresh_stats(
                update_chart=True, update_text_feeds=True, update_dashboard_periods=True),
            fg_color=T.BG_INNER, button_color=T.BG_INNER,
            button_hover_color=T.BG_BORDER, text_color=T.TEXT_HEAD,
            dropdown_fg_color=T.BG_SURFACE, dropdown_hover_color=T.BG_BORDER,
            dropdown_text_color=T.TEXT_HEAD,
        )
        self.report_period_menu.grid(row=0, column=1, padx=(0, 12), pady=8)
        ctk.CTkLabel(actions, text="Export Format", text_color=T.TEXT_HEAD).grid(
            row=0, column=2, padx=(0, 8), pady=8)
        self.report_format_menu = ctk.CTkOptionMenu(
            actions,
            values=["csv", "pdf"],
            variable=self.report_format_var,
            command=lambda _value: self._update_report_summary(),
            fg_color=T.BG_INNER, button_color=T.BG_INNER,
            button_hover_color=T.BG_BORDER, text_color=T.TEXT_HEAD,
            dropdown_fg_color=T.BG_SURFACE, dropdown_hover_color=T.BG_BORDER,
            dropdown_text_color=T.TEXT_HEAD,
        )
        self.report_format_menu.grid(row=0, column=3, padx=(0, 12), pady=8)
        ctk.CTkButton(actions, text="Export Report", corner_radius=8,
                      fg_color=T.ACCENT, hover_color=T.ACCENT_HOVER,
                      text_color=T.TEXT_HEAD,
                      command=self._export_report).grid(row=0, column=4, pady=8)
        ctk.CTkLabel(actions, textvariable=self.report_export_status_var,
                     fg_color=T.BADGE_BG, corner_radius=999, padx=12, pady=5,
                     text_color=T.ACCENT_TEXT, font=ctk.CTkFont(size=11),
                     ).grid(row=0, column=5, padx=(12, 0), pady=8, sticky="e")

        chart_frame = ctk.CTkFrame(body, fg_color=T.BG_INNER, corner_radius=12,
                                   border_width=1, border_color=T.BG_BORDER)
        chart_frame.grid(row=2, column=0, padx=16, pady=(0, 12), sticky="ew")
        ctk.CTkLabel(chart_frame, text="Read vs Unread",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=T.TEXT_HEAD).pack(anchor="w", padx=14, pady=(10, 4))
        self._reports_chart_host = tk.Frame(chart_frame, bg=T.resolve(T.BG_INNER), height=180)
        self._reports_chart_host.pack(fill="x", padx=8, pady=(0, 12))
        self._reports_chart = ReportsChart(self._reports_chart_host)

        ctk.CTkLabel(body, text="Recent Delivery Activity",
                     font=ctk.CTkFont(size=14, weight="bold"),
                     text_color=T.TEXT_HEAD).grid(
            row=3, column=0, padx=16, pady=(4, 8), sticky="w")
        self.reports_text = ctk.CTkTextbox(
            body, fg_color=T.BG_INNER, border_width=1, border_color=T.BG_BORDER,
            text_color=T.TEXT_MUTED, font=ctk.CTkFont(size=12))
        self.reports_text.grid(row=4, column=0, padx=16, pady=(0, 16), sticky="nsew")
        self._replace_text(self.reports_text, "No tracked messages yet.")

    def _build_campaign_history_view(self) -> None:
        frame = self._new_view_container("History", scrollable=True)
        frame.grid_columnconfigure(0, weight=1)

        hero = ctk.CTkFrame(frame, fg_color=T.BG_SURFACE, corner_radius=14,
                            border_width=1, border_color=T.BG_BORDER)
        # Item 28 (Final Premium Polish Pass): was pady=(0, 10), the sole
        # outlier -- every other top-level hero/toolbar card app-wide
        # (Campaigns home, Contacts, Reports & Analytics) uses (0, 12).
        hero.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        hero.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(hero, text="Campaign history",
                     font=ctk.CTkFont(size=15, weight="bold"),
                     text_color=T.TEXT_HEAD).grid(
            row=0, column=0, padx=16, pady=(14, 4), sticky="w")
        ctk.CTkLabel(hero, text="Full log of all email campaigns. Use Duplicate to re-use a campaign.",
                     text_color=T.TEXT_MUTED, font=ctk.CTkFont(size=12),
                     ).grid(row=1, column=0, padx=16, pady=(0, 14), sticky="w")
        ctk.CTkButton(hero, text="Export CSV", width=100, height=30, corner_radius=6,
                      fg_color=T.ACCENT, hover_color=T.ACCENT_HOVER, text_color=T.TEXT_HEAD,
                      font=ctk.CTkFont(size=11), command=self._export_campaigns_csv,
                      ).grid(row=0, column=1, rowspan=2, padx=18, pady=14, sticky="e")

        list_frame = ctk.CTkFrame(frame, fg_color=T.BG_SURFACE, corner_radius=14,
                                  border_width=1, border_color=T.BG_BORDER)
        list_frame.grid(row=1, column=0, sticky="nsew")
        list_frame.grid_columnconfigure(0, weight=1)
        list_frame.grid_rowconfigure(0, weight=1)
        frame.grid_rowconfigure(1, weight=1)

        scroll = ctk.CTkScrollableFrame(list_frame, fg_color="transparent")
        scroll.grid(row=0, column=0, sticky="nsew", padx=12, pady=12)
        scroll.grid_columnconfigure(0, weight=1)
        self._bind_scrollable_frame_mousewheel(scroll)

        self._history_scroll = scroll
        self._history_campaigns = self.db.get_recent_campaigns_summary(limit=100)
        self._render_history_rows()

    def _render_history_rows(self, query: str = "") -> None:
        if not hasattr(self, "_history_scroll"):
            return
        for child in self._history_scroll.winfo_children():
            child.destroy()

        q = query.strip().lower()
        campaigns = [c for c in self._history_campaigns
                     if not q or q in (c.get("name") or "").lower()]

        if not campaigns:
            title = "No campaigns match that search" if q else "No campaign history yet"
            subtitle = ("Try a different search term."
                        if q else
                        "Start an email campaign from Compose to see it here.")
            empty = ctk.CTkFrame(self._history_scroll, fg_color=T.BG_INNER, corner_radius=12,
                                 border_width=1, border_color=T.BG_BORDER)
            empty.grid(row=0, column=0, sticky="ew", padx=6, pady=6)
            ctk.CTkLabel(empty, text=title, font=ctk.CTkFont(size=14, weight="bold"),
                         text_color=T.TEXT_HEAD).pack(padx=16, pady=(16, 4), anchor="w")
            ctk.CTkLabel(empty, text=subtitle,
                         text_color=T.TEXT_MUTED).pack(padx=16, pady=(0, 16), anchor="w")
            return

        STATUS_COLORS = {"sent": T.SUCCESS, "failed": T.DANGER_ON_BADGE, "draft": T.TEXT_MUTED}
        for index, camp in enumerate(campaigns):
            row_frame = ctk.CTkFrame(self._history_scroll, fg_color=T.BG_INNER, corner_radius=10,
                                     border_width=1, border_color=T.BG_BORDER)
            row_frame.grid(row=index, column=0, sticky="ew", pady=4)
            row_frame.grid_columnconfigure(1, weight=1)

            name = camp.get("name", "Untitled")
            created = camp.get("created_at", "")
            sent = camp.get("sent_count", 0)
            failed = camp.get("failed_count", 0)
            bounced = camp.get("bounced_count", 0)
            status = "sent" if sent > 0 else "failed" if failed > 0 else "draft"

            ctk.CTkLabel(row_frame, text=name,
                         font=ctk.CTkFont(size=13, weight="bold"),
                         text_color=T.TEXT_HEAD).grid(
                row=0, column=0, padx=14, pady=(10, 2), sticky="w")
            summary_text = f"📅 {created}  ·  ✅ {sent} sent  ·  ❌ {failed} failed"
            if bounced:
                summary_text += f"  ·  🚫 {bounced} bounced"
            ctk.CTkLabel(row_frame, text=summary_text,
                         text_color=T.TEXT_MUTED, font=ctk.CTkFont(size=11),
                         ).grid(row=1, column=0, padx=14, pady=(0, 10), sticky="w")
            ctk.CTkLabel(row_frame, text=status, fg_color=T.BADGE_BG, corner_radius=999,
                         padx=10, pady=4,
                         text_color=STATUS_COLORS.get(status, T.TEXT_MUTED),
                         font=ctk.CTkFont(size=10),
                         ).grid(row=0, column=1, padx=14, pady=(10, 2), sticky="e")

            actions = ctk.CTkFrame(row_frame, fg_color="transparent")
            actions.grid(row=1, column=1, padx=14, pady=(0, 10), sticky="e")

            def duplicate(c=camp):
                self._em_subj_var.set(c.get("message_template", ""))
                self._compose_channel_var.set("Email")
                self._on_channel_switch("Email")
                self._show_view("Compose")

            # Item 12 of the Live Testing Findings pass (Round 2): the old
            # fg_color=T.BADGE_BG fill was measured at only ~1.2:1 contrast
            # against this row's own T.BG_INNER background (the two tokens
            # are near-identical shades in both Dark and Light) -- the
            # button's own rectangular shape was nearly invisible, which is
            # exactly why it read as plain text rather than a clickable
            # button. Fixed by matching the outline-button style already
            # established elsewhere in the app (e.g. Compose's Pause/Resume
            # button): a real border + accent-colored text, which measures
            # a real 3.2:1-4.0:1 contrast against T.BG_INNER regardless of
            # theme, instead of relying on fill-color contrast that doesn't
            # exist here.
            ctk.CTkButton(actions, text="↻ Duplicate", width=100, corner_radius=6,
                          fg_color="transparent", hover_color=T.BG_BORDER,
                          border_width=1, border_color=T.ACCENT,
                          text_color=T.ACCENT_TEXT, font=ctk.CTkFont(size=11, weight="bold"),
                          command=duplicate).pack(side="left", padx=4)

            if sent > 0 and camp.get("id") is not None:
                bounce_btn = ctk.CTkButton(
                    actions, text="🔍 Check Bounces", width=124, corner_radius=6,
                    fg_color="transparent", hover_color=T.BG_BORDER,
                    border_width=1, border_color=T.ACCENT,
                    text_color=T.ACCENT_TEXT, font=ctk.CTkFont(size=11, weight="bold"))

                def check_bounces(campaign_id=camp.get("id"), btn=bounce_btn):
                    btn.configure(state="disabled", text="Checking…")

                    def on_done(check_result):
                        if not btn.winfo_exists():
                            return
                        btn.configure(state="normal", text="🔍 Check Bounces")
                        if check_result is not None and not check_result.ok:
                            show_toast(self, f"Bounce check failed: {check_result.error}", kind="error")

                    self._check_campaign_for_bounces(campaign_id, silent=False, on_done=on_done)

                bounce_btn.configure(command=check_bounces)
                bounce_btn.pack(side="left", padx=4)

    def _export_campaigns_csv(self) -> None:
        import csv
        from tkinter import filedialog
        campaigns = self.db.get_recent_campaigns_summary(limit=9999)
        if not campaigns:
            messagebox.showinfo("No data", "No campaigns to export.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")],
            initialfile="campaigns.csv",
            title="Save campaign history as CSV",
        )
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(
                    f, fieldnames=["id", "name", "created_at", "sent_count", "failed_count"])
                writer.writeheader()
                for camp in campaigns:
                    writer.writerow({k: camp.get(k, "") for k in writer.fieldnames})
            self._log_activity(f"Campaign history exported to CSV ({len(campaigns)} rows)")
            show_toast(self, f"Saved {len(campaigns)} campaigns to {os.path.basename(path)}", kind="success")
        except Exception as exc:
            messagebox.showerror("Export failed", str(exc))

    def _build_settings_view(self) -> None:
        frame = self._new_view_container("Settings", scrollable=True)
        frame.grid_columnconfigure((0, 1), weight=1, uniform="settings")

        hero = ctk.CTkFrame(frame, fg_color=T.BG_SURFACE, corner_radius=14,
                            border_width=1, border_color=T.BG_BORDER)
        hero.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        hero.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(hero, text="Settings",
                     font=ctk.CTkFont(size=15, weight="bold"),
                     text_color=T.TEXT_HEAD).grid(
            row=0, column=0, padx=16, pady=(14, 4), sticky="w")
        ctk.CTkLabel(hero, text="Tune cadence, safety guardrails, appearance, and activation.",
                     text_color=T.TEXT_MUTED, font=ctk.CTkFont(size=12)).grid(
            row=1, column=0, padx=16, pady=(0, 14), sticky="w")
        hero_chips = ctk.CTkFrame(hero, fg_color="transparent")
        hero_chips.grid(row=0, column=1, rowspan=2, padx=16, pady=14, sticky="e")
        for index, variable in enumerate(
                [self.settings_delay_chip_var, self.settings_theme_chip_var,
                 self.settings_guard_chip_var]):
            ctk.CTkLabel(hero_chips, textvariable=variable, fg_color=T.BADGE_BG,
                         corner_radius=999, padx=12, pady=5,
                         text_color=T.ACCENT_TEXT, font=ctk.CTkFont(size=11),
                         ).grid(row=0, column=index, padx=5)

        card = ctk.CTkFrame(frame, fg_color=T.BG_SURFACE, corner_radius=14,
                            border_width=1, border_color=T.BG_BORDER)
        card.grid(row=1, column=0, sticky="nsew", padx=(0, 8))
        card.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(card, text="Campaign Safety",
                     font=ctk.CTkFont(size=15, weight="bold"),
                     text_color=T.TEXT_HEAD).grid(
            row=0, column=0, columnspan=3, padx=16, pady=(16, 4), sticky="w")
        ctk.CTkLabel(card, text="Rate limits and guardrails for stable sending.",
                     text_color=T.TEXT_MUTED, font=ctk.CTkFont(size=12)).grid(
            row=1, column=0, columnspan=3, padx=16, pady=(0, 14), sticky="w")

        delay_lbl = ctk.CTkLabel(card, text="Delay between messages", text_color=T.TEXT_HEAD)
        delay_lbl.grid(row=2, column=0, padx=16, pady=10, sticky="w")
        add_tooltip(delay_lbl, "How long to wait after each message before sending the next "
                                "one. Longer delays look more human and are less likely to get "
                                "your account flagged or blocked.")
        self.delay_slider = ctk.CTkSlider(card, from_=10, to=120, number_of_steps=110, command=self._on_delay_change)
        self.delay_slider.grid(row=2, column=1, padx=16, pady=10, sticky="ew")
        self.delay_slider.set(self.delay_var.get())
        self.delay_label = ctk.CTkLabel(card, text=f"{self.delay_var.get()} sec",
                                        text_color=T.TEXT_MUTED)
        self.delay_label.grid(row=2, column=2, padx=(0, 16), pady=10, sticky="e")

        limit_lbl = ctk.CTkLabel(card, text="Daily limit", text_color=T.TEXT_HEAD)
        limit_lbl.grid(row=3, column=0, padx=16, pady=10, sticky="w")
        add_tooltip(limit_lbl, "The maximum number of messages this app will send in one "
                                "campaign/day. Keeping this low reduces the risk of your "
                                "WhatsApp or email account being flagged.")
        self.limit_slider = ctk.CTkSlider(card, from_=10, to=500, number_of_steps=98, command=self._on_daily_limit_change)
        self.limit_slider.grid(row=3, column=1, padx=16, pady=10, sticky="ew")
        self.limit_slider.set(self.daily_limit_var.get())
        self.limit_label = ctk.CTkLabel(card, text=str(self.daily_limit_var.get()),
                                        text_color=T.TEXT_MUTED)
        self.limit_label.grid(row=3, column=2, padx=(0, 16), pady=10, sticky="e")

        self.limit_warning_label = ctk.CTkLabel(card, text="", text_color=T.DANGER_ON_BADGE,
                                                font=ctk.CTkFont(size=11), wraplength=360, justify="left")
        self.limit_warning_label.grid(row=4, column=0, columnspan=3, padx=16, pady=(0, 12), sticky="w")

        # Item 30 (Final Premium Polish Pass): every CTkSwitch/CTkCheckBox/
        # CTkRadioButton app-wide previously left CTk's own stock default
        # theme colors untouched (fg_color/progress_color ['#3B8ED0',
        # '#1F6AA5'] -- a generic blue), confirmed directly against
        # ctk.ThemeManager.theme, clashing with this app's own indigo
        # T.ACCENT (#6366F1) used everywhere else (buttons, active nav,
        # badges) -- a real "unbranded stock widget" tell. The WhatsApp
        # panel's own "Select all contacts"/"Consent confirmed" checkboxes
        # (main_window.py ~1641) already had the right recipe; applied here
        # and to every other switch/checkbox/radio app-wide to match.
        _switch_style = dict(fg_color=T.BG_BORDER, progress_color=T.ACCENT,
                              button_color=T.TEXT_HEAD, button_hover_color=T.TEXT_MUTED)
        jitter_switch = ctk.CTkSwitch(card, text="Random jitter", variable=self.jitter_var,
                      text_color=T.TEXT_HEAD, command=self._save_settings, **_switch_style)
        jitter_switch.grid(row=5, column=0, padx=16, pady=10, sticky="w")
        add_tooltip(jitter_switch, "Adds a small random variation to the delay between "
                                    "messages instead of a perfectly even gap — makes sending "
                                    "look more natural and less like an automated bot.")
        consent_switch = ctk.CTkSwitch(card, text="Consent required", variable=self.consent_required_var,
                      text_color=T.TEXT_HEAD, command=self._save_settings, **_switch_style)
        consent_switch.grid(row=5, column=1, padx=16, pady=10, sticky="w")
        add_tooltip(consent_switch, "When on, you must confirm you have recipients' consent "
                                     "before every send — required in most places for bulk "
                                     "email/WhatsApp messaging.")

        def _on_warmup_toggle() -> None:
            self._save_settings()
            self._update_email_warmup_status_label()

        warmup_switch = ctk.CTkSwitch(card, text="Email warm-up mode",
                      variable=self.email_warmup_enabled_var,
                      text_color=T.TEXT_HEAD, command=_on_warmup_toggle, **_switch_style)
        warmup_switch.grid(row=6, column=0, columnspan=2, padx=16, pady=(10, 0), sticky="w")
        add_tooltip(warmup_switch, "Ramps a new/unproven email account's daily send cap up "
                                    "gradually over the first 14 days instead of allowing your "
                                    "full daily limit from day one — reduces the risk of a new "
                                    "sending account getting throttled or flagged. Turn this off "
                                    "once your account has an established sending history.")
        self.email_warmup_status_label = ctk.CTkLabel(
            card, text="", text_color=T.TEXT_MUTED, font=ctk.CTkFont(size=11),
            wraplength=360, justify="left")
        self.email_warmup_status_label.grid(
            row=7, column=0, columnspan=3, padx=16, pady=(2, 0), sticky="w")

        self.reputation_label = ctk.CTkLabel(
            card, text="", text_color=T.TEXT_MUTED, font=ctk.CTkFont(size=11, weight="bold"),
            wraplength=360, justify="left")
        self.reputation_label.grid(
            row=8, column=0, columnspan=3, padx=16, pady=(6, 14), sticky="w")
        add_tooltip(self.reputation_label,
                    "A basic, honest recommendation combining your warm-up ramp with any real, "
                    "recently-logged send failures — never recommends more than your warm-up cap "
                    "allows. With no send history yet, this shows the ramp's conservative "
                    "starting point, not fabricated data.")

        system_card = ctk.CTkFrame(frame, fg_color=T.BG_SURFACE, corner_radius=14,
                                   border_width=1, border_color=T.BG_BORDER)
        system_card.grid(row=1, column=1, sticky="nsew", padx=(8, 0))
        system_card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(system_card, text="System Experience",
                     font=ctk.CTkFont(size=15, weight="bold"),
                     text_color=T.TEXT_HEAD).grid(
            row=0, column=0, padx=16, pady=(16, 4), sticky="w")
        ctk.CTkLabel(system_card, text="Theme, session state, and workspace recovery controls.",
                     text_color=T.TEXT_MUTED, font=ctk.CTkFont(size=12)).grid(
            row=1, column=0, padx=16, pady=(0, 14), sticky="w")
        theme_lbl = ctk.CTkLabel(system_card, text="Theme selector", text_color=T.TEXT_HEAD)
        theme_lbl.grid(row=2, column=0, padx=16, pady=(0, 6), sticky="w")
        add_tooltip(theme_lbl, "Dark and Light follow your choice everywhere in the app. "
                                "System matches your Windows setting automatically. Warm Ivory "
                                "is a warmer, paper-like light theme as a third option.")
        self.theme_menu = ctk.CTkOptionMenu(
            system_card,
            values=["Dark", "Light", "Warm Ivory", "System"],
            variable=self.theme_var,
            command=self._on_theme_selected,
            fg_color=T.BG_INNER, button_color=T.BG_INNER,
            button_hover_color=T.BG_BORDER, text_color=T.TEXT_HEAD,
            dropdown_fg_color=T.BG_SURFACE, dropdown_hover_color=T.BG_BORDER,
            dropdown_text_color=T.TEXT_HEAD,
        )
        self.theme_menu.grid(row=3, column=0, padx=16, pady=(0, 12), sticky="w")

        session_strip = ctk.CTkFrame(system_card, fg_color=T.BG_INNER, corner_radius=12,
                                     border_width=1, border_color=T.BG_BORDER)
        session_strip.grid(row=4, column=0, padx=16, pady=(0, 12), sticky="ew")
        ctk.CTkLabel(session_strip, text="Session Status",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=T.TEXT_HEAD).pack(anchor="w", padx=14, pady=(12, 4))
        ctk.CTkLabel(session_strip, textvariable=self.session_status_var,
                     text_color=T.TEXT_MUTED, wraplength=360, justify="left").pack(
            anchor="w", padx=14, pady=(0, 8))
        self.connect_whatsapp_btn = ctk.CTkButton(
            session_strip, text="🔗 Connect WhatsApp", corner_radius=8,
            fg_color=T.ACCENT, hover_color=T.ACCENT_HOVER, text_color=T.TEXT_HEAD,
            command=self._connect_whatsapp_now)
        self.connect_whatsapp_btn.pack(anchor="w", padx=14, pady=(0, 14))

        wa_risk_banner = ctk.CTkFrame(system_card, fg_color=T.BADGE_BG, corner_radius=10,
                                      border_width=1, border_color=T.DANGER)
        wa_risk_banner.grid(row=5, column=0, padx=16, pady=(0, 12), sticky="ew")
        ctk.CTkLabel(wa_risk_banner, text="⚠ WhatsApp ban risk at high volume",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color=T.DANGER_ON_BADGE).pack(anchor="w", padx=12, pady=(10, 2))
        ctk.CTkLabel(
            wa_risk_banner,
            text="Unofficial/automated WhatsApp sending at high volume (hundreds-to-thousands "
                 "per day) on a personal number is very likely to get that number banned — this "
                 "is a WhatsApp policy and detection reality, not something any app's code can "
                 "fully prevent. Keep daily volume conservative, use real delays between "
                 "messages, and treat a connected number as replaceable, not permanent.",
            text_color=T.TEXT_MUTED, font=ctk.CTkFont(size=11),
            wraplength=380, justify="left").pack(anchor="w", padx=12, pady=(0, 10))

        system_actions = ctk.CTkFrame(system_card, fg_color="transparent")
        system_actions.grid(row=6, column=0, padx=16, pady=(0, 16), sticky="w")
        ctk.CTkButton(system_actions, text="Re-run Setup Wizard", corner_radius=8,
                      fg_color=T.ACCENT, hover_color=T.ACCENT_HOVER,
                      text_color=T.TEXT_HEAD,
                      command=self._reopen_setup_wizard).pack(side="left", padx=(0, 8))
        # Item 39 v2: same on-demand-help tier as "Re-run Setup Wizard" right
        # next to it — outline-secondary styling (matches History's
        # "Duplicate" button / Compose's Pause-Resume, Item 27's own
        # established secondary-action recipe) since this isn't the primary
        # action on this card. Toggles the same Tour Mode as the header "?".
        ctk.CTkButton(system_actions, text="🧭 Take a Tour", corner_radius=8,
                      fg_color=T.BG_INNER, hover_color=T.BG_BORDER,
                      border_width=1, border_color=T.BG_BORDER,
                      text_color=T.ACCENT_TEXT,
                      command=lambda: self.tour_mode.toggle()).pack(side="left")

        license_card = ctk.CTkFrame(frame, fg_color=T.BG_SURFACE, corner_radius=14,
                                    border_width=1, border_color=T.BG_BORDER)
        license_card.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        license_card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(license_card, text="License & Activation",
                     font=ctk.CTkFont(size=15, weight="bold"),
                     text_color=T.TEXT_HEAD).grid(
            row=0, column=0, padx=16, pady=(16, 6), sticky="w")
        self.settings_license_label = ctk.CTkLabel(
            license_card, textvariable=self.license_status_var,
            text_color=T.TEXT_MUTED, justify="left", wraplength=700)
        self.settings_license_label.grid(row=1, column=0, padx=16, pady=(0, 12), sticky="w")

        premium_strip = ctk.CTkFrame(license_card, fg_color=T.BG_INNER, corner_radius=12)
        premium_strip.grid(row=2, column=0, padx=16, pady=(0, 12), sticky="ew")
        premium_strip.grid_columnconfigure((0, 1, 2), weight=1)
        for index, (title, value) in enumerate([
            ("Plan", "Premium"),
            ("Session", "Persistent"),
            ("Reports", "Export Ready"),
        ]):
            tile = ctk.CTkFrame(premium_strip, fg_color=T.BADGE_BG, corner_radius=10)
            tile.grid(row=0, column=index, padx=8, pady=10, sticky="ew")
            ctk.CTkLabel(tile, text=title, text_color=T.TEXT_MUTED,
                         font=ctk.CTkFont(size=11)).pack(anchor="w", padx=12, pady=(10, 2))
            ctk.CTkLabel(tile, text=value,
                         font=ctk.CTkFont(size=14, weight="bold"),
                         text_color=T.ACCENT_TEXT).pack(anchor="w", padx=12, pady=(0, 12))

        license_actions = ctk.CTkFrame(license_card, fg_color="transparent")
        license_actions.grid(row=3, column=0, padx=16, pady=(0, 16), sticky="ew")
        license_actions.grid_columnconfigure(1, weight=1)
        self.settings_activate_button = ctk.CTkButton(
            license_actions,
            text="Activate License",
            fg_color=T.ACCENT,
            hover_color=T.ACCENT_HOVER,
            text_color=T.TEXT_HEAD,
            text_color_disabled=T.TEXT_MUTED,
            command=self._show_license_gate,
        )
        self.settings_activate_button.grid(row=0, column=0, padx=(0, 10), sticky="w")
        self.settings_deactivate_button = ctk.CTkButton(
            license_actions,
            text="Deactivate License",
            fg_color=T.DANGER,
            hover_color=T.DANGER_HOVER,
            text_color=T.TEXT_HEAD,
            text_color_disabled=T.TEXT_MUTED,
            command=self._deactivate_license,
        )
        self.settings_deactivate_button.grid(row=0, column=1, padx=(0, 10), sticky="w")
        self.settings_license_chip = ctk.CTkLabel(
            license_actions,
            textvariable=self.license_badge_var,
            fg_color=T.BADGE_BG,
            corner_radius=999,
            padx=12,
            pady=6,
            text_color=T.ACCENT_TEXT,
            font=ctk.CTkFont(size=11, weight="bold"),
        )
        self.settings_license_chip.grid(row=0, column=2, sticky="e")

        # ── Email — SMTP settings ─────────────────────────────────────────────
        smtp_card = ctk.CTkFrame(frame, fg_color=T.BG_SURFACE, corner_radius=14,
                                 border_width=1, border_color=T.BG_BORDER)
        smtp_card.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        smtp_card.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(smtp_card, text="Email — SMTP",
                     font=ctk.CTkFont(size=15, weight="bold"),
                     text_color=T.TEXT_HEAD).grid(
            row=0, column=0, columnspan=2, padx=16, pady=(16, 4), sticky="w")
        ctk.CTkLabel(smtp_card,
                     text="Credentials used when sending email from the Compose screen.",
                     text_color=T.TEXT_MUTED, font=ctk.CTkFont(size=12)).grid(
            row=1, column=0, columnspan=2, padx=16, pady=(0, 12), sticky="w")

        SMTP_PRESETS = {
            "Gmail":   ("smtp.gmail.com", "587"),
            "Outlook": ("smtp-mail.outlook.com", "587"),
            "Yahoo":   ("smtp.mail.yahoo.com", "587"),
            "Custom":  ("", "587"),
        }

        def _on_preset(val):
            h, p = SMTP_PRESETS.get(val, ("", "587"))
            self._em_host.set(h)
            self._em_port.set(p)
            self._save_settings()

        provider_lbl = ctk.CTkLabel(smtp_card, text="Provider", text_color=T.TEXT_HEAD)
        provider_lbl.grid(row=2, column=0, padx=16, pady=6, sticky="w")
        add_tooltip(provider_lbl, "Pick your email provider to auto-fill the Host and Port "
                                   "below. Choose Custom if you use a different provider or "
                                   "your own mail server.")
        self.smtp_provider_menu = ctk.CTkOptionMenu(
            smtp_card, values=list(SMTP_PRESETS.keys()),
            variable=self._em_provider, command=_on_preset,
            fg_color=T.BG_INNER, button_color=T.BG_INNER,
            button_hover_color=T.BG_BORDER, text_color=T.TEXT_HEAD,
            dropdown_fg_color=T.BG_SURFACE, dropdown_hover_color=T.BG_BORDER,
            dropdown_text_color=T.TEXT_HEAD)
        self.smtp_provider_menu.grid(row=2, column=1, padx=(4, 16), pady=6, sticky="ew")

        for i, (lbl, var, secret, tip) in enumerate([
            ("Host",         self._em_host,      False,
             "Your email provider's outgoing mail server address, e.g. smtp.gmail.com. "
             "Check your provider's help pages if you're not sure."),
            ("Port",         self._em_port,      False,
             "The connection port for outgoing mail — usually 587. If sending fails, try 465."),
            ("Username",     self._em_user,      False,
             "Usually your full email address."),
            ("Password",     self._em_pass,      True,
             "For Gmail/Outlook this is often an app password, not your regular login "
             "password — check your provider's security settings to generate one."),
            ("Sender name",  self._em_from_name, False,
             "The name recipients see in their inbox, e.g. your business name."),
            ("Sender email", self._em_from_addr, False,
             "Must match the email account you're sending from."),
            ("Delay (sec)",  self._em_delay,     False,
             "Seconds to wait between each email — spreads sends out so your account "
             "isn't flagged as spam."),
        ], start=3):
            lbl_widget = ctk.CTkLabel(smtp_card, text=lbl, text_color=T.TEXT_HEAD)
            lbl_widget.grid(row=i, column=0, padx=16, pady=5, sticky="w")
            add_tooltip(lbl_widget, tip)
            entry = ctk.CTkEntry(smtp_card, textvariable=var, show="●" if secret else "",
                                 fg_color=T.BG_INNER, border_color=T.BG_BORDER,
                                 text_color=T.TEXT_HEAD)
            entry.grid(row=i, column=1, padx=(4, 16), pady=5, sticky="ew")
            entry.bind("<FocusOut>", lambda _e: self._save_settings())
            entry.bind("<Return>",   lambda _e: self._save_settings())

        ctk.CTkButton(smtp_card, text="Test connection",
                      fg_color=T.ACCENT, hover_color=T.ACCENT_HOVER, corner_radius=8,
                      text_color=T.TEXT_HEAD,
                      command=self._test_smtp_connection).grid(
            row=10, column=0, columnspan=2, padx=16, pady=(10, 16), sticky="w")

        # ── AI Cards — BYO API key ────────────────────────────────────────────
        ai_card = ctk.CTkFrame(frame, fg_color=T.BG_SURFACE, corner_radius=14,
                               border_width=1, border_color=T.BG_BORDER)
        ai_card.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        ai_card.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(ai_card, text="AI Cards — API Key",
                     font=ctk.CTkFont(size=15, weight="bold"),
                     text_color=T.TEXT_HEAD).grid(
            row=0, column=0, columnspan=3, padx=16, pady=(16, 4), sticky="w")
        ctk.CTkLabel(ai_card,
                     text="Bring your own API key to unlock AI-assisted card copy and "
                          "per-contact personalization. Stored encrypted on this device "
                          "only — never sent anywhere except direct calls to your provider.",
                     text_color=T.TEXT_MUTED, font=ctk.CTkFont(size=12),
                     wraplength=700, justify="left").grid(
            row=1, column=0, columnspan=3, padx=16, pady=(0, 12), sticky="w")

        provider_lbl = ctk.CTkLabel(ai_card, text="AI provider", text_color=T.TEXT_HEAD)
        provider_lbl.grid(row=2, column=0, padx=16, pady=6, sticky="w")
        add_tooltip(provider_lbl, "Which AI provider generates card copy and personalized "
                                    "messages. Google Gemini has a genuine free tier if you "
                                    "don't want to pay for Anthropic Claude.")
        provider_labels = list(ai_service.PROVIDER_LABELS.values())
        provider_keys_by_label = {v: k for k, v in ai_service.PROVIDER_LABELS.items()}

        ai_key_lbl = ctk.CTkLabel(ai_card, text="API key", text_color=T.TEXT_HEAD)

        def _update_ai_key_tooltip():
            provider = self._ai_provider.get()
            if provider == "gemini":
                add_tooltip(ai_key_lbl, "Get a free-tier key from aistudio.google.com/apikey "
                                         "(no fixed prefix format). Stored encrypted on this "
                                         "device only and is never sent anywhere except "
                                         "directly to Google when generating content.")
            else:
                add_tooltip(ai_key_lbl, "Get this from console.anthropic.com — starts with "
                                         "\"sk-ant-...\". Stored encrypted on this device only "
                                         "and is never sent anywhere except directly to "
                                         "Anthropic when generating content.")

        def _on_provider_change(label: str) -> None:
            self._ai_provider.set(provider_keys_by_label.get(label, "anthropic"))
            _update_ai_key_tooltip()
            self._ai_billing_note_var.set(ai_service.billing_note(self._ai_provider.get()))
            self._save_settings()

        self.ai_provider_menu = ctk.CTkOptionMenu(
            ai_card, values=provider_labels,
            command=_on_provider_change, fg_color=T.BG_INNER, button_color=T.BG_INNER,
            button_hover_color=T.BG_BORDER, text_color=T.TEXT_HEAD,
            dropdown_fg_color=T.BG_SURFACE, dropdown_hover_color=T.BG_BORDER,
            dropdown_text_color=T.TEXT_HEAD)
        provider_menu = self.ai_provider_menu
        provider_menu.set(ai_service.PROVIDER_LABELS.get(self._ai_provider.get(), provider_labels[0]))
        provider_menu.grid(row=2, column=1, columnspan=2, padx=(4, 16), pady=6, sticky="ew")

        ai_key_lbl.grid(row=3, column=0, padx=16, pady=6, sticky="w")
        _update_ai_key_tooltip()
        self._ai_key_entry = ctk.CTkEntry(
            ai_card, textvariable=self._ai_api_key, show="●",
            fg_color=T.BG_INNER, border_color=T.BG_BORDER, text_color=T.TEXT_HEAD)
        self._ai_key_entry.grid(row=3, column=1, padx=(4, 8), pady=6, sticky="ew")

        def _toggle_ai_key_visible():
            visible = not self._ai_key_visible.get()
            self._ai_key_visible.set(visible)
            self._ai_key_entry.configure(show="" if visible else "●")
            self._ai_key_toggle_btn.configure(text="Hide" if visible else "Show")

        self._ai_key_toggle_btn = ctk.CTkButton(
            ai_card, text="Show", width=70, corner_radius=8,
            fg_color=T.BG_INNER, hover_color=T.BG_BORDER, text_color=T.TEXT_HEAD,
            command=_toggle_ai_key_visible)
        self._ai_key_toggle_btn.grid(row=3, column=2, padx=(0, 16), pady=6, sticky="e")

        # Item 15 of the Live Testing Findings pass (Round 2): "premium
        # onboarding" for the API key field -- a real clickable link to the
        # correct provider's key-creation page (dynamic on the provider
        # dropdown above, read at click time so it always matches whatever
        # is currently selected), a plain-language helper line, and a pay-
        # as-you-go/billing note, so a correctly-saved key that still fails
        # isn't confusing.
        def _open_key_creation_page():
            webbrowser.open(ai_service.key_creation_url(self._ai_provider.get()))

        get_key_row = ctk.CTkFrame(ai_card, fg_color="transparent")
        get_key_row.grid(row=4, column=0, columnspan=3, padx=16, pady=(0, 2), sticky="ew")
        ctk.CTkButton(
            get_key_row, text="Get an API key →", width=140, height=26, corner_radius=8,
            fg_color="transparent", hover_color=T.BADGE_BG, text_color=T.ACCENT_TEXT,
            font=ctk.CTkFont(size=12, weight="bold"), anchor="w",
            command=_open_key_creation_page).pack(side="left")
        ctk.CTkLabel(
            get_key_row,
            text="Click above to create an account and generate a key, then paste it here.",
            text_color=T.TEXT_MUTED, font=ctk.CTkFont(size=11)).pack(side="left", padx=(10, 0))

        self._ai_billing_note_var = StringVar(value=ai_service.billing_note(self._ai_provider.get()))
        ctk.CTkLabel(ai_card, textvariable=self._ai_billing_note_var, text_color=T.TEXT_DIM,
                     font=ctk.CTkFont(size=11), wraplength=700, justify="left").grid(
            row=5, column=0, columnspan=3, padx=16, pady=(0, 12), sticky="w")

        def _save_ai_key():
            self._save_settings()
            self._ai_key_status_var.set(
                "API key saved (encrypted)" if self._ai_api_key.get() else "No API key saved")

        def _clear_ai_key():
            self._ai_api_key.set("")
            _save_ai_key()

        self._ai_key_entry.bind("<FocusOut>", lambda _e: _save_ai_key())
        self._ai_key_entry.bind("<Return>",   lambda _e: _save_ai_key())

        ai_actions = ctk.CTkFrame(ai_card, fg_color="transparent")
        ai_actions.grid(row=6, column=0, columnspan=3, padx=16, pady=(0, 16), sticky="ew")
        ctk.CTkButton(ai_actions, text="Save key", corner_radius=8,
                      fg_color=T.ACCENT, hover_color=T.ACCENT_HOVER, text_color=T.TEXT_HEAD,
                      command=_save_ai_key).pack(side="left", padx=(0, 10))
        ctk.CTkButton(ai_actions, text="Clear key", corner_radius=8,
                      fg_color=T.DANGER, hover_color=T.DANGER_HOVER, text_color=T.TEXT_HEAD,
                      command=_clear_ai_key).pack(side="left", padx=(0, 10))

        def _test_ai_key():
            api_key = self._ai_api_key.get()
            if not api_key:
                messagebox.showwarning("No API key", "Save an API key first.")
                return

            test_key_btn.configure(state="disabled", text="Testing…")

            def worker():
                try:
                    ai_service.validate_api_key(api_key, provider=self._ai_provider.get())
                except AIServiceError as ex:
                    # Computed here, not inside the deferred lambda -- `ex` is
                    # auto-deleted by Python at except-block exit, before
                    # self.after()'s callback runs; referencing it there
                    # raised a NameError Tk's default handler silently
                    # swallowed (stderr only) -- this is the real root cause
                    # of "Test key"/"Generate with AI" appearing to do
                    # nothing (or show a stale/blank result) on failure.
                    error_message = str(ex)
                    self.after(0, lambda: finish(False, error_message))
                    return
                self.after(0, lambda: finish(True, "Key is valid ✅"))

            def finish(ok: bool, message: str) -> None:
                test_key_btn.configure(state="normal", text="Test key")
                if ok:
                    messagebox.showinfo("AI key test", message)
                else:
                    messagebox.showerror("AI key test failed", message)

            threading.Thread(target=worker, daemon=True).start()

        test_key_btn = ctk.CTkButton(ai_actions, text="Test key", corner_radius=8,
                      fg_color=T.BG_INNER, hover_color=T.BG_BORDER, text_color=T.TEXT_HEAD,
                      command=_test_ai_key)
        test_key_btn.pack(side="left", padx=(0, 10))
        ctk.CTkLabel(ai_actions, textvariable=self._ai_key_status_var,
                     text_color=T.TEXT_MUTED, font=ctk.CTkFont(size=12)).pack(side="left")

        danger_card = ctk.CTkFrame(frame, fg_color=T.BG_SURFACE, corner_radius=14,
                                   border_width=1, border_color=T.DANGER)
        danger_card.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        danger_card.grid_columnconfigure((0, 1, 2), weight=1)
        ctk.CTkLabel(danger_card, text="Danger Zone",
                     font=ctk.CTkFont(size=15, weight="bold"),
                     text_color=T.DANGER_ON_BADGE).grid(
            row=0, column=0, columnspan=3, padx=16, pady=(16, 4), sticky="w")
        ctk.CTkLabel(danger_card,
                     text="These actions permanently delete data and cannot be undone.",
                     text_color=T.TEXT_MUTED, font=ctk.CTkFont(size=12)).grid(
            row=1, column=0, columnspan=3, padx=16, pady=(0, 14), sticky="w")

        def _danger_row(col: int, label: str, desc: str, command) -> None:
            cell = ctk.CTkFrame(danger_card, fg_color=T.BG_INNER, corner_radius=10,
                                border_width=1, border_color=T.BG_BORDER)
            cell.grid(row=2, column=col, padx=16, pady=(0, 16), sticky="new")
            ctk.CTkLabel(cell, text=label, text_color=T.TEXT_HEAD,
                         font=ctk.CTkFont(size=13, weight="bold")).pack(
                anchor="w", padx=14, pady=(12, 2))
            ctk.CTkLabel(cell, text=desc, text_color=T.TEXT_MUTED, font=ctk.CTkFont(size=11),
                         wraplength=170, justify="left").pack(anchor="w", padx=14, pady=(0, 10))
            ctk.CTkButton(cell, text=label, corner_radius=8, height=30,
                          fg_color=T.DANGER, hover_color=T.DANGER_HOVER, text_color=T.TEXT_HEAD,
                          font=ctk.CTkFont(size=11), command=command).pack(
                anchor="w", padx=14, pady=(0, 12))

        _danger_row(
            0, "Reset Session", "Clears the saved WhatsApp login — you'll need to scan a QR code again.",
            lambda: show_danger_confirm(
                self, "Reset WhatsApp Session",
                "This clears your saved WhatsApp login. You'll need to scan a QR code again "
                "before sending any WhatsApp messages.",
                "RESET", "Reset Session", self._do_reset_session))
        _danger_row(
            1, "Delete All Contacts", "Permanently removes every saved contact from this app.",
            lambda: show_danger_confirm(
                self, "Delete All Contacts",
                f"This permanently deletes all {len(self.contacts)} saved contacts. "
                "This cannot be undone — export a backup first if you're not sure.",
                "DELETE", "Delete All Contacts", self._do_delete_all_contacts))
        _danger_row(
            2, "Clear Campaign History", "Permanently removes all past campaign and send records.",
            lambda: show_danger_confirm(
                self, "Clear Campaign History",
                "This permanently deletes every campaign and message log record. "
                "This cannot be undone.",
                "DELETE", "Clear History", self._do_clear_campaign_history))

        multi_wa_card = ctk.CTkFrame(frame, fg_color=T.BG_SURFACE, corner_radius=14,
                                     border_width=1, border_color=T.BG_BORDER)
        multi_wa_card.grid(row=6, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        multi_wa_card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(multi_wa_card, text="WhatsApp Multi-Number (Experimental)",
                     font=ctk.CTkFont(size=15, weight="bold"),
                     text_color=T.TEXT_HEAD).grid(
            row=0, column=0, padx=16, pady=(16, 4), sticky="w")
        ctk.CTkLabel(
            multi_wa_card,
            text="Configure additional numbers here so each gets its own isolated, persisted "
                 "login. Not yet wired into live sending — a campaign still uses the one "
                 "connected number in the WhatsApp panel above. Rotating sends across multiple "
                 "real numbers needs testing against real WhatsApp accounts, which isn't "
                 "available in this environment.",
            text_color=T.TEXT_MUTED, font=ctk.CTkFont(size=11),
            wraplength=700, justify="left").grid(
            row=1, column=0, padx=16, pady=(0, 12), sticky="w")

        self.wa_accounts_list_frame = ctk.CTkFrame(multi_wa_card, fg_color="transparent")
        self.wa_accounts_list_frame.grid(row=2, column=0, padx=16, pady=(0, 10), sticky="ew")

        add_row = ctk.CTkFrame(multi_wa_card, fg_color="transparent")
        add_row.grid(row=3, column=0, padx=16, pady=(0, 16), sticky="w")
        self._wa_new_account_var = StringVar(value="")
        add_entry = ctk.CTkEntry(add_row, textvariable=self._wa_new_account_var, width=220,
                                  placeholder_text="e.g. Sales Line",
                                  fg_color=T.BG_INNER, border_color=T.BG_BORDER,
                                  text_color=T.TEXT_HEAD)
        add_entry.pack(side="left", padx=(0, 8))
        add_entry.bind("<Return>", lambda _e: self._add_whatsapp_account())
        ctk.CTkButton(add_row, text="+ Add Account", corner_radius=8, height=32,
                      fg_color=T.ACCENT, hover_color=T.ACCENT_HOVER, text_color=T.TEXT_HEAD,
                      command=self._add_whatsapp_account).pack(side="left")

        self._render_whatsapp_accounts()

        self._update_settings_summary()
        self._update_daily_limit_warning()
        self._update_email_warmup_status_label()

    def _build_status_bar(self) -> None:
        """Round 2 item 8: JobMind Match's real `.footer-status-bar`
        (styles.css:458, "Fixed Copilot-style status bar — always visible
        at bottom") -- a full-width bar fixed to the bottom of the whole
        window, not a sidebar-only element. The earlier reference-research
        checkpoint's claim of a `<footer class="app-footer premium-footer">`
        was itself wrong (grepped JobMind's actual templates/CSS again for
        this pass -- no such class exists anywhere); `.footer-status-bar` is
        the real thing, confirmed via `dashboard.html:2103`:
        `JobMind <em>Premium</em> · ● Live · v{version} · 100% On Your
        Machine · © 2026 Muhammad Faraz`.

        Built once here (not inside _create_ui) and never destroyed: unlike
        the sidebar/content, this bar's content doesn't depend on the
        active view, so it doesn't need rebuilding on Warm Ivory
        transitions. Its colors use plain T.token tuples, so it picks up
        every theme change (Dark/Light natively, Warm Ivory via the same
        (value, value) tuple mechanism) with zero extra code, same as any
        other CTk-native widget in this app.

        Placed in a new grid row=1 (columnspan=2, weight=0) below the
        existing sidebar+content row=0 (weight=1) -- a fixed-height row
        pinned to the bottom of a non-scrolling desktop window is the
        direct equivalent of CSS `position:fixed;bottom:0` for this stack.
        """
        bar = ctk.CTkFrame(self, fg_color=T.BG_MAIN, corner_radius=0,
                            border_width=1, border_color=T.BG_BORDER, height=28)
        bar.grid(row=1, column=0, columnspan=2, sticky="ew")
        bar.grid_propagate(False)

        row = ctk.CTkFrame(bar, fg_color="transparent")
        row.pack(expand=True)

        def sep() -> None:
            ctk.CTkLabel(row, text="·", text_color=T.TEXT_DIM,
                         font=ctk.CTkFont(size=10)).pack(side="left", padx=6)

        ctk.CTkLabel(row, text=APP_NAME, text_color=T.TEXT_HEAD,
                     font=ctk.CTkFont(size=10, weight="bold")).pack(side="left")
        sep()

        live_group = ctk.CTkFrame(row, fg_color="transparent")
        live_group.pack(side="left")
        self._status_bar_dot = tk.Canvas(
            live_group, width=8, height=8, highlightthickness=0, bg=T.resolve(T.BG_MAIN))
        self._status_bar_dot.pack(side="left", padx=(0, 4))
        self._status_bar_dot_item = self._status_bar_dot.create_oval(
            1, 1, 7, 7, fill=T.resolve(T.SUCCESS), outline="")
        ctk.CTkLabel(live_group, text="Live", text_color=T.TEXT_DIM,
                     font=ctk.CTkFont(size=10)).pack(side="left")
        sep()

        ctk.CTkLabel(row, text=f"v{APP_VERSION}", text_color=T.TEXT_DIM,
                     font=ctk.CTkFont(size=10)).pack(side="left")
        sep()

        ctk.CTkLabel(row, text="100% On Your Device", text_color=T.TEXT_DIM,
                     font=ctk.CTkFont(size=10)).pack(side="left")
        sep()

        ctk.CTkLabel(row, text=f"© {datetime.now().year} {DEVELOPER}",
                     text_color=T.TEXT_DIM, font=ctk.CTkFont(size=10)).pack(side="left")

        self._status_bar_dot_pulse_after_id = None
        self._start_status_bar_dot_pulse()

    def _start_status_bar_dot_pulse(self) -> None:
        """Same color-alternation technique as the sidebar update pill's dot
        (see _start_update_dot_pulse) -- standing in for JobMind's CSS
        opacity-pulse keyframe on `.footer-status-dot`, which Tk canvas
        items can't do directly (no alpha channel)."""
        if getattr(self, "_status_bar_dot_pulse_after_id", None) is not None:
            return
        dot = getattr(self, "_status_bar_dot", None)
        if dot is None:
            return

        def step(lit: bool) -> None:
            if not dot.winfo_exists():
                self._status_bar_dot_pulse_after_id = None
                return
            try:
                dot.itemconfig(
                    self._status_bar_dot_item,
                    fill=T.resolve(T.SUCCESS) if lit else T.resolve(T.BG_MAIN))
            except Exception:
                self._status_bar_dot_pulse_after_id = None
                return
            self._status_bar_dot_pulse_after_id = self.after(1000, lambda: step(not lit))

        step(True)

    def _new_view_frame(self, name: str) -> ctk.CTkFrame:
        return self._new_view_container(name)

    def _new_view_container(self, name: str, scrollable: bool = False) -> ctk.CTkFrame:
        frame_class = ctk.CTkScrollableFrame if scrollable else ctk.CTkFrame
        frame = frame_class(self.view_host, fg_color=T.BG_MAIN, corner_radius=0)
        self.view_frames[name] = frame
        container = getattr(frame, "_parent_frame", frame)
        container.grid(row=0, column=0, sticky="nsew")
        container.grid_remove()
        self.view_containers[name] = container
        if scrollable:
            self._bind_scrollable_frame_mousewheel(frame)
        return frame

    # Views whose widget tree is expensive enough that Tk's own redraw cost
    # (not this animation's logic — measured directly, see CLAUDE.md) blows
    # the transition time budget on every hidden->visible switch regardless
    # of animation step count: an instant grid() swap is used for these
    # instead of _animate_view_in(). Currently just Compose (dual WA/Email
    # panels + a live contact checkbox list); re-measure before removing a
    # view from this set if its content is ever substantially simplified.
    _HEAVY_VIEWS_NO_ANIMATION = {"Compose"}

    def _toggle_sidebar_collapsed(self) -> None:
        self._sidebar_collapsed = not self._sidebar_collapsed
        self._apply_sidebar_collapsed_visuals()
        self._save_settings()

    def _pulse_collapse_toggle(self) -> None:
        """Brief accent-color flash on the collapse button itself, timed
        with the instant width snap -- a single widget's own .configure()
        call doesn't force any layout pass (unlike the width change this
        stands in for), so it's effectively free. Cancels any pulse already
        in flight from a rapid double-click first."""
        prev_after_id = getattr(self, "_collapse_pulse_after_id", None)
        if prev_after_id is not None:
            try:
                self.after_cancel(prev_after_id)
            except Exception:
                pass
            self._collapse_pulse_after_id = None
        btn = self.sidebar_collapse_btn
        try:
            btn.configure(fg_color=T.ACCENT, text_color=T.TEXT_HEAD)
        except Exception:
            return

        def restore() -> None:
            self._collapse_pulse_after_id = None
            try:
                btn.configure(fg_color=T.NAV_INACTIVE, text_color=T.TEXT_MUTED)
            except Exception:
                pass

        self._collapse_pulse_after_id = self.after(150, restore)

    def _apply_sidebar_collapsed_visuals(self) -> None:
        """Snap instantly between expanded/icon-only, no width animation.

        Round 2 item 1 asked this to match JobMind Match's real
        `transition: width 0.15s ease` on its sidebar -- measured directly
        (not assumed) before deciding against it: stepping
        grid_columnconfigure(0, minsize=...) from 220 to 72 costs ~40-210ms
        PER STEP on this app's real views (Cards, Compose, Settings), even
        with the content pane's own column pinned to a fixed width so it
        doesn't have to reflow too. A single step already blows the ~90ms
        budget the view slide-in animation uses elsewhere in this file, and
        that's with column 1 (content) held fixed -- the real toggle can't
        do that, since the content pane's available width genuinely does
        change. A smooth multi-step version would cost seconds, not
        milliseconds, and would visibly reflow whatever heavy view (Cards,
        Compose, Settings) happens to be showing on every single frame. An
        instant toggle is the honest, measured choice, not a guessed one.

        What WAS feasible and is new this pass: a dynamic tooltip mirroring
        JobMind's `toggle.title = collapsed ? "Expand..." : "Collapse..."`,
        and a brief single-widget color pulse on the toggle button itself
        (no relayout, just two .configure() calls) so the click still gets
        some tactile feedback instead of a bare instant snap."""
        collapsed = self._sidebar_collapsed
        self.grid_columnconfigure(
            0, minsize=self.SIDEBAR_WIDTH_COLLAPSED if collapsed else self.SIDEBAR_WIDTH_EXPANDED)
        self.sidebar_collapse_btn.configure(text="»" if collapsed else "«")
        self._collapse_btn_tooltip.text = (
            "Expand sidebar" if collapsed else "Collapse sidebar")
        self._pulse_collapse_toggle()

        # Brand wordmark + every informational (non-actionable) bottom
        # widget hide entirely when collapsed -- none of them fit
        # meaningfully at 72px, and none are things a user needs to act on
        # at a glance. The collapse toggle itself always stays reachable.
        # The 58x58 logo image is included here too -- real bug found via
        # winfo_width() instrumentation (not just style/const comparison):
        # the logo alone (58px + its own 10px grid padding) already exceeds
        # the entire SIDEBAR_WIDTH_COLLAPSED budget, so leaving it visible
        # meant the collapsed sidebar never actually reached 72px no matter
        # what else shrank -- it silently floated around ~150-160px instead.
        # See CLAUDE.md "cold-start sidebar position bug" checkpoint.
        for widget in (self._brand_title_label, self._brand_subtitle_label,
                       self._brand_logo_label):
            if widget is None:
                continue
            if collapsed:
                widget.grid_remove()
            else:
                widget.grid()

        # Order matters here: side="bottom" packing stacks each newly-packed
        # widget ABOVE the previously-packed ones, so this must replay the
        # same order _create_ui() originally packed them in (license_badge,
        # then session_status_label, then premium_panel) or a collapse ->
        # re-expand round trip silently reverses their visual stacking —
        # found by comparing before/after screenshots, not by reading the
        # code (the bug was invisible in isolation, only visible as a diff).
        for widget, pack_kwargs in (
            (self.sidebar_license_badge, dict(side="bottom", anchor="w", padx=12, pady=(0, 14))),
            (self.sidebar_session_status_label, dict(side="bottom", fill="x", padx=12, pady=(4, 3))),
            (self.sidebar_premium_panel, dict(side="bottom", fill="x", padx=10, pady=(0, 6))),
        ):
            if collapsed:
                widget.pack_forget()
            else:
                widget.pack(**pack_kwargs)

        if collapsed:
            self._update_badge_slot.pack_forget()
            self._stop_update_dot_pulse()
        else:
            self._update_badge_slot.pack(side="top", fill="x")
            if self._update_info is not None:
                self._refresh_update_badge()

        for view_name, (icon, label) in self.sidebar_nav_meta.items():
            button = self.sidebar_buttons.get(view_name)
            if button is not None:
                button.configure(
                    text=icon if collapsed else f"{icon}  {label}",
                    anchor="center" if collapsed else "w",
                )

    def _cancel_pending_view_animation(self) -> None:
        """Cancel any in-flight _animate_view_in transition and hide its
        container immediately.

        Real bug this closes: _animate_view_in used to be the only place
        that cancelled a stale in-flight animation, so the
        _HEAVY_VIEWS_NO_ANIMATION fast path in _show_view (a bare
        container.grid(), no call to _animate_view_in) never cancelled
        anything. A view mid-slide-in is managed by place(), not grid(), so
        _show_view's grid_remove() cleanup loop silently did nothing to it
        -- it stayed visible, floating on top of whatever heavy view got
        shown next. Bumping _view_anim_run_id also guarantees any already
        in-flight step() closure (captured before after_cancel could reach
        it) is a guaranteed no-op if it still somehow fires.
        """
        prev_after_id = getattr(self, "_view_anim_after_id", None)
        if prev_after_id is not None:
            try:
                self.after_cancel(prev_after_id)
            except Exception:
                pass
            self._view_anim_after_id = None
        prev_container = getattr(self, "_view_anim_container", None)
        if prev_container is not None:
            try:
                prev_container.place_forget()
            except Exception:
                pass
            self._view_anim_container = None
        self._view_anim_run_id = getattr(self, "_view_anim_run_id", 0) + 1

    def _show_view(self, view_name: str) -> None:
        self._active_view = view_name
        self._apply_view_chrome(view_name)
        self.header_title.configure(text=view_name)
        incoming = self.view_containers.get(view_name)
        # A still-in-flight _animate_view_in transition leaves its container
        # under place() management, not grid() -- the grid_remove() loop
        # below is a no-op against a container place() owns, so it would
        # stay visible (mid-slide) on top of whatever we show next. Must
        # cancel it *unconditionally* here, not only inside _animate_view_in
        # itself, because the _HEAVY_VIEWS_NO_ANIMATION fast path below
        # never calls _animate_view_in at all and so never touched this
        # state before. Real bug: tests/ui/test_view_stacking.py failed on
        # {Campaigns,Settings,History}->Compose specifically (the source
        # views light/fast enough that update() returns before the ~90ms
        # animation's after()-scheduled steps are due) but not
        # {Contacts,Cards}->Compose (heavy enough that update() happens to
        # outlast the animation) -- a real timing race, not a per-view quirk.
        if incoming is not getattr(self, "_view_anim_container", None):
            self._cancel_pending_view_animation()
        for name, frame in self.view_containers.items():
            if name == view_name:
                continue
            frame.grid_remove()
        if incoming is not None:
            if view_name in self._HEAVY_VIEWS_NO_ANIMATION:
                incoming.grid()
            else:
                self._animate_view_in(incoming)
        for name, button in self.sidebar_buttons.items():
            is_active = name == view_name
            button.configure(
                fg_color=T.ACCENT if is_active else T.NAV_INACTIVE,
                hover_color=T.ACCENT_HOVER if is_active else T.BG_SURFACE,
                border_width=1,
                border_color=T.ACCENT if is_active else T.NAV_INACTIVE,
                text_color=T.TEXT_HEAD,
                font=ctk.CTkFont(size=13, weight="bold" if is_active else "normal"),
            )
            if name in self.sidebar_accent_bars:
                bar = self.sidebar_accent_bars[name]
                if is_active:
                    self._animate_nav_accent_in(bar)
                else:
                    self._draw_nav_accent(bar, active=False)
        if view_name == "Campaigns":
            self._refresh_campaigns_home()
        elif view_name in ("Contacts", "History"):
            self._on_header_search()
        elif view_name == "Reports":
            self._refresh_stats(update_chart=True, update_text_feeds=True, update_dashboard_periods=True)
        elif view_name in {"Compose", "Dashboard"}:
            self._refresh_stats(
                update_text_feeds=(view_name == "Dashboard"),
                update_dashboard_periods=True,
            )
        if view_name == "Compose":
            self._refresh_preview()

    # Matches the fixed height= the accent-bar Canvas is constructed with in
    # _create_ui — used as a constant instead of querying winfo_height() live,
    # see _draw_nav_accent's docstring for why that query was actually removed.
    _NAV_ACCENT_HEIGHT = 40
    _NAV_ACCENT_WIDTH = 4

    # Item 13 of the Live Testing Findings pass (Round 2): the nav accent
    # bar's own reveal (_animate_nav_accent_in) and the content slide
    # (_animate_view_in) both fire from the same _show_view call, at the
    # same instant, and are meant to read as one cohesive arrival -- but
    # they used to run on two different clocks (5 steps/120ms, linear, for
    # the accent bar vs 4 steps/90ms, ease_out_cubic, for the content),
    # found via direct code review, not a screenshot: the accent bar was
    # still visibly growing in for ~30ms after the content had already
    # finished easing into place, on a different acceleration curve the
    # whole time they overlapped. Both animations now share the exact same
    # step/duration constants and easing function so they can't drift apart
    # again.
    _VIEW_TRANSITION_STEPS = 4
    _VIEW_TRANSITION_DURATION_MS = 90

    @staticmethod
    def _ease_out_cubic(t: float) -> float:
        return 1 - (1 - t) ** 3

    def _draw_nav_accent(self, canvas: tk.Canvas, active: bool, reveal_frac: float = 1.0) -> None:
        """Paint the sidebar nav accent bar. Inactive: flat background (item
        not selected). Active: a top-to-bottom ACCENT->SUCCESS gradient,
        Career Copilot's blue->teal pill-nav underline reinterpreted as a
        vertical bar since our sidebar is vertical, not a horizontal pill row
        (see CLAUDE.md "Sidebar redesign" for the full pattern mapping) —
        built only from existing theme.py tokens, no new hex values.
        `reveal_frac` (0..1) paints only the top fraction of the bar, used by
        _animate_nav_accent_in for a short grow-in instead of an instant snap.

        Uses the known-fixed canvas height/width as constants rather than
        `canvas.update_idletasks()` + `winfo_height()` — an earlier version
        queried live geometry here and it was a real, measured regression:
        `update_idletasks()` flushes *all* pending Tk idle tasks app-wide, not
        just this ~4px canvas, and since this runs from inside `_show_view`
        (right as a new, possibly heavy view like Cards/Compose/Settings is
        being laid out), it forced that view's layout to complete synchronously
        right at the worst possible moment — measured pushing Cards' transition
        from ~250ms to 870-1740ms in tests/ui/test_navigation_timing.py before
        being caught and fixed here."""
        bg = T.resolve(T.BG_MAIN)
        canvas.configure(bg=bg)
        canvas.delete("all")
        if not active:
            return
        height = self._NAV_ACCENT_HEIGHT
        width = self._NAV_ACCENT_WIDTH
        painted = max(1, int(height * max(0.0, min(1.0, reveal_frac))))
        top_r, top_g, top_b = (c >> 8 for c in canvas.winfo_rgb(T.resolve(T.ACCENT)))
        bot_r, bot_g, bot_b = (c >> 8 for c in canvas.winfo_rgb(T.resolve(T.SUCCESS)))
        for y in range(painted):
            t = y / max(height - 1, 1)
            r = int(top_r + (bot_r - top_r) * t)
            g = int(top_g + (bot_g - top_g) * t)
            b = int(top_b + (bot_b - top_b) * t)
            canvas.create_line(0, y, width, y, fill=f"#{r:02x}{g:02x}{b:02x}")

    def _animate_nav_accent_in(self, canvas: tk.Canvas) -> None:
        """Short grow-in reveal for the active nav item's accent bar, standing
        in for Copilot's 180ms CSS transition on its pill-nav active state —
        Tk has no CSS transitions, so this steps reveal_frac 0->1 by hand.
        Same discipline as _animate_view_in: cheap because only this ~4px-wide
        canvas redraws (no sibling relayout), tight step count, and a hard
        wall-clock deadline so a slow machine just finishes slightly early
        rather than ever blocking. Shares _VIEW_TRANSITION_STEPS/_DURATION_MS
        and _ease_out_cubic with _animate_view_in -- see that pair's own
        comment for the real timing/easing mismatch this closes."""
        if self._nav_accent_anim_after_id is not None:
            try:
                self.after_cancel(self._nav_accent_anim_after_id)
            except Exception:
                pass
            self._nav_accent_anim_after_id = None

        steps = self._VIEW_TRANSITION_STEPS
        duration_ms = self._VIEW_TRANSITION_DURATION_MS
        start = time.time()
        deadline = start + 0.22

        def step(i: int) -> None:
            if not canvas.winfo_exists() or time.time() > deadline:
                self._draw_nav_accent(canvas, active=True, reveal_frac=1.0)
                self._nav_accent_anim_after_id = None
                return
            frac = self._ease_out_cubic((i + 1) / steps)
            self._draw_nav_accent(canvas, active=True, reveal_frac=frac)
            if i + 1 >= steps:
                self._nav_accent_anim_after_id = None
                return
            self._nav_accent_anim_after_id = self.after(duration_ms // steps, lambda: step(i + 1))

        step(0)

    def _animate_view_in(self, container: ctk.CTkFrame) -> None:
        """Signature navigation transition: the incoming view slides up into
        place from a slight vertical offset, eased out, over ~90ms (the
        docstring here previously said "~150ms" -- stale relative to the
        actual duration_ms constant below; found and fixed during Item 13's
        code-level review). This is a deliberately scoped-down "own
        interpretation" of a shatter/3D-flip transition — CustomTkinter/Tk
        has no per-widget alpha compositing (only whole-Toplevel -alpha), so
        a true shatter or a cross-fade between two live widget trees isn't
        achievable without rendering both to images first (fragile,
        platform-specific, and risks exactly the flicker/glitches this
        feature is supposed to avoid). The outgoing view is hidden instantly
        rather than animated out, for the same reason. See CLAUDE.md for the
        full writeup of this decision.

        Shares its step count, duration, and easing curve with the sidebar's
        own _animate_nav_accent_in (both _VIEW_TRANSITION_STEPS/_DURATION_MS
        and _ease_out_cubic) -- they fire from the same _show_view call, at
        the same instant, and are meant to read as one arrival, not two.

        Position-only (relx/rely), size held fixed at relwidth=relheight=1.0:
        an earlier version also animated relwidth/relheight for a scale
        effect, but measured 700ms-1.8s on complex views (Settings, Cards)
        because changing a place()'d container's SIZE forces Tk to re-run
        grid/pack layout for every nested child on every single frame.
        Changing only its on-screen POSITION does not — children never see a
        different available size, so there's nothing to relayout, just a
        cheap re-blit. A hard wall-clock deadline is kept as a safety net
        regardless, so a slow machine degrades to "snaps into place a little
        early" rather than ever blocking longer than the promised budget.
        """
        # If a previous animation is still in flight (rapid nav clicking, or
        # a HEAVY_VIEWS_NO_ANIMATION target that bypassed this method
        # entirely), cancel its pending step and hide its container
        # immediately so it doesn't finish animating into view later. See
        # _cancel_pending_view_animation's own docstring for the real bug
        # this closes (place()-managed containers surviving a grid_remove()
        # cleanup pass) and _show_view's call site for why this can't only
        # live here.
        if getattr(self, "_view_anim_container", None) is not container:
            self._cancel_pending_view_animation()
        anim_id = getattr(self, "_view_anim_run_id", 0) + 1
        self._view_anim_run_id = anim_id
        self._view_anim_container = container

        steps = self._VIEW_TRANSITION_STEPS
        duration_ms = self._VIEW_TRANSITION_DURATION_MS
        interval = max(8, duration_ms // steps)
        start_dy = 0.04
        hard_deadline = time.time() + 0.22  # never block longer than this, any hardware

        container.grid()
        container.update_idletasks()

        def finalize() -> None:
            self._view_anim_after_id = None
            try:
                container.place_forget()
                container.grid()
            except Exception:
                pass

        def step(i: int) -> None:
            if self._view_anim_run_id != anim_id:
                return  # superseded by a newer navigation
            if time.time() > hard_deadline:
                finalize()
                return
            t = i / steps
            eased = self._ease_out_cubic(t)
            dy = start_dy * (1 - eased)
            try:
                container.place(relx=0, rely=dy, relwidth=1.0, relheight=1.0)
            except Exception:
                return
            if i < steps:
                self._view_anim_after_id = self.after(interval, lambda: step(i + 1))
            else:
                finalize()

        step(0)

    def _apply_view_chrome(self, view_name: str) -> None:
        view_meta = {
            "Campaigns": (
                "Your campaign workspace — start a new send or review recent activity.",
                "Campaign home",
            ),
            "History": (
                "Full log of every campaign — duplicate, re-schedule, or export any entry.",
                "Campaign history",
            ),
            "Dashboard": (
                "Persistent WhatsApp sessions, delivery analytics, and safer campaigns.",
                "Campaign home",
            ),
            "Contacts": (
                "Organize your outreach directory with searchable, campaign-ready contact records.",
                "Contacts",
            ),
            "Compose": (
                "Write a message, pick your channel and recipients, then send.",
                "Compose",
            ),
            "Reports": (
                "Track sent, delivered, and read performance from a live monitoring workspace.",
                "Reports",
            ),
            "Email": (
                "Send HTML email campaigns with templates and variable substitution.",
                "Email",
            ),
            "Cards": (
                "Build marketing cards for any app — WhatsApp, email, social.",
                "Card creator",
            ),
            "Settings": (
                "Tune cadence, safety guardrails, SMTP, sessions, and activation.",
                "Settings",
            ),
        }
        subtitle, badge = view_meta.get(view_name, view_meta["Campaigns"])
        self.header_context_var.set(subtitle)
        self.header_badge_var.set(badge)

    def _load_settings(self) -> None:
        settings = self.db.get_setting_json(
            self.SETTINGS_KEY,
            {"theme": "Warm Ivory", "delay": 30, "daily_limit": 50, "jitter": True, "consent_required": True},
        )
        self.theme_var.set(str(settings.get("theme", "Warm Ivory")))
        self.delay_var.set(int(settings.get("delay", 30)))
        self.daily_limit_var.set(int(settings.get("daily_limit", 50)))
        self.jitter_var.set(bool(settings.get("jitter", True)))
        self.consent_required_var.set(bool(settings.get("consent_required", True)))
        self.email_warmup_enabled_var.set(bool(settings.get("email_warmup_enabled", True)))
        self._email_warmup_start_date = str(settings.get("email_warmup_start_date", ""))

        # SMTP — host/user/etc are low-sensitivity and stay plain; the password
        # is encrypted at rest with the same Fernet key as the AI API key.
        # Falls back to the old plaintext "smtp_pass" key for anyone upgrading
        # from a version that saved it that way, so existing users don't have
        # to re-enter their password after this change.
        # Real bug found via a live end-to-end send test: a stray trailing
        # newline in a stored field (almost certainly from a clipboard paste
        # into a Settings entry -- a plain CTkEntry doesn't let you *type* a
        # literal "\n", but pasting one in is possible) reached smtplib's
        # real "From" header construction unstripped and raised "folded
        # header contains newline", silently failing every single email
        # send. .strip() here self-heals any already-corrupted stored value
        # on the very next load; _save_settings below also strips so a
        # fresh paste can't reintroduce it.
        self._em_provider.set(str(settings.get("smtp_provider", "Gmail")).strip())
        self._em_host.set(str(settings.get("smtp_host", "smtp.gmail.com")).strip())
        self._em_port.set(str(settings.get("smtp_port", "587")).strip())
        self._em_user.set(str(settings.get("smtp_user", "")).strip())
        smtp_pass = decrypt_secret(str(settings.get("smtp_pass_enc", "")))
        if not smtp_pass:
            smtp_pass = str(settings.get("smtp_pass", ""))  # legacy plaintext fallback
        self._em_pass.set(smtp_pass)
        self._em_from_name.set(str(settings.get("smtp_from_name", "My Business")).strip())
        self._em_from_addr.set(str(settings.get("smtp_from_addr", "")).strip())
        self._em_delay.set(str(settings.get("smtp_delay", "5")).strip())

        # AI Cards API key — encrypted at rest, decrypted only into memory here
        ai_key = decrypt_secret(str(settings.get("ai_api_key_enc", "")))
        self._ai_api_key.set(ai_key)
        self._ai_provider.set(str(settings.get("ai_provider", "anthropic")))
        self._ai_key_status_var.set("API key saved (encrypted)" if ai_key else "No API key saved")

        # First-run setup wizard progress (plain attrs, not Tk Variables —
        # nothing binds to these continuously, only read/written at step transitions)
        self.setup_wizard_completed = bool(settings.get("setup_wizard_completed", False))
        self.setup_wizard_skipped = bool(settings.get("setup_wizard_skipped", False))
        self.setup_wizard_channels = list(settings.get("setup_wizard_channels", []))
        self.setup_wizard_channel_index = int(settings.get("setup_wizard_channel_index", 0))
        self.setup_wizard_substep = str(settings.get("setup_wizard_substep", ""))
        self._sidebar_collapsed = bool(settings.get("sidebar_collapsed", False))

    def _save_settings(self) -> None:
        self.db.set_setting_json(
            self.SETTINGS_KEY,
            {
                "theme": self.theme_var.get(),
                "delay": self.delay_var.get(),
                "daily_limit": self.daily_limit_var.get(),
                "jitter": self.jitter_var.get(),
                "consent_required": self.consent_required_var.get(),
                "email_warmup_enabled": self.email_warmup_enabled_var.get(),
                "email_warmup_start_date": self._email_warmup_start_date,
                # SMTP
                "smtp_provider":   self._em_provider.get().strip(),
                "smtp_host":       self._em_host.get().strip(),
                "smtp_port":       self._em_port.get().strip(),
                "smtp_user":       self._em_user.get().strip(),
                "smtp_pass_enc":   encrypt_secret(self._em_pass.get()),
                "smtp_from_name":  self._em_from_name.get().strip(),
                "smtp_from_addr":  self._em_from_addr.get().strip(),
                "smtp_delay":      self._em_delay.get().strip(),
                # AI Cards
                "ai_api_key_enc":  encrypt_secret(self._ai_api_key.get()),
                "ai_provider":     self._ai_provider.get(),
                # Setup wizard progress
                "setup_wizard_completed":     self.setup_wizard_completed,
                "setup_wizard_skipped":       self.setup_wizard_skipped,
                "setup_wizard_channels":      self.setup_wizard_channels,
                "setup_wizard_channel_index": self.setup_wizard_channel_index,
                "setup_wizard_substep":       self.setup_wizard_substep,
                "sidebar_collapsed":          self._sidebar_collapsed,
            },
        )
        self._update_settings_summary()
        self._refresh_stats(update_text_feeds=True, update_dashboard_periods=True)

    def _apply_theme(self, selected_theme: str) -> None:
        prev_palette = T.get_palette()
        has_ui = hasattr(self, "view_host")
        # Item 14 of the Live Testing Findings pass (Round 2): measured
        # directly (not guessed) before fixing -- CustomTkinter's own
        # ctk_base_class.py._set_appearance_mode() calls update_idletasks()
        # once per live CTk widget on every ctk.set_appearance_mode() call.
        # With ~540+ CTk widgets alive at once (every view is built upfront
        # for fast navigation, not just the active one), that's ~540+
        # sequential partial-screen-repaint flushes, measured at
        # 350-1000ms wall-clock for set_appearance_mode() alone depending
        # on system load -- real code inside the installed library, not
        # something in this app that can be patched. That's what actually
        # produces the reported "flickers through multiple inconsistent
        # visual states": the visible view repaints color-by-color across
        # that whole window instead of atomically. Mitigated the same way
        # the close-button fix hid its own slow teardown (self.withdraw()
        # first): cover the screen with a solid, already-correct destination
        # color BEFORE the slow propagation starts, so the many incremental
        # partial redraws happen unseen behind it, then reveal once done.
        if has_ui:
            self._show_theme_switch_overlay(selected_theme)

        if selected_theme == "Warm Ivory":
            T.set_palette("warm_ivory")
            ctk.set_appearance_mode("Light")
        else:
            ctk.set_appearance_mode(selected_theme)  # "Dark" / "Light" / "System"
            T.set_palette("light" if ctk.get_appearance_mode() == "Light" else "dark")
        new_palette = T.get_palette()

        if not has_ui:
            return  # still inside __init__, before _create_ui() — nothing to refresh yet

        # Warm Ivory is a genuine 3rd palette CTk's binary appearance mode can't
        # represent — already-built widgets can't pick it up in place, so a full
        # rebuild is required entering or leaving it (see theme.py docstring).
        entering_or_leaving_warm = (prev_palette == "warm_ivory") != (new_palette == "warm_ivory")
        if entering_or_leaving_warm:
            self.after_idle(self._rebuild_ui_for_theme_and_hide_overlay)
        else:
            self.after_idle(self._sync_theme_overrides_and_hide_overlay)

    def _theme_switch_overlay_color(self, selected_theme: str) -> str:
        """The DESTINATION background color, computed before the actual
        mode switch happens (T.resolve() only knows the CURRENT mode)."""
        if selected_theme == "System":
            try:
                import darkdetect
                resolved_mode = "Dark" if darkdetect.theme() == "Dark" else "Light"
            except Exception:
                resolved_mode = "Dark"
            return T.bg_main_for_mode(resolved_mode)
        return T.bg_main_for_mode(selected_theme)

    def _show_theme_switch_overlay(self, selected_theme: str) -> None:
        color = self._theme_switch_overlay_color(selected_theme)
        if self._theme_switch_overlay is None or not self._theme_switch_overlay.winfo_exists():
            self._theme_switch_overlay = tk.Frame(self, bg=color, highlightthickness=0, bd=0)
        else:
            self._theme_switch_overlay.configure(bg=color)
        self._theme_switch_overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
        self._theme_switch_overlay.lift()
        # One deliberate, single flush -- paints the overlay itself and gets
        # it covering the screen NOW, before the slow ~540-widget
        # propagation storm begins below it. The opposite of the bug this
        # fixes: one cheap forced redraw, not hundreds.
        self._theme_switch_overlay.update_idletasks()

    def _hide_theme_switch_overlay(self) -> None:
        if self._theme_switch_overlay is not None and self._theme_switch_overlay.winfo_exists():
            self._theme_switch_overlay.place_forget()

    def _sync_theme_overrides_and_hide_overlay(self) -> None:
        self._sync_theme_overrides()
        self._hide_theme_switch_overlay()

    def _rebuild_ui_for_theme_and_hide_overlay(self) -> None:
        if self._theme_switch_overlay is not None and self._theme_switch_overlay.winfo_exists():
            self._theme_switch_overlay.lift()
        self._rebuild_ui_for_theme()
        self._hide_theme_switch_overlay()

    def _rebuild_ui_for_theme(self) -> None:
        """Full sidebar+content rebuild — the only way to apply Warm Ivory
        (or leave it) to already-constructed widgets. Rare action (theme
        switch), so the rebuild cost is an acceptable, documented tradeoff."""
        prev_view = getattr(self, "_active_view", "Campaigns")
        self.sidebar.destroy()
        self.content.destroy()
        self._create_ui()
        self._sync_theme_overrides()
        self._reload_contacts()
        self._refresh_stats(update_text_feeds=True, update_dashboard_periods=True)
        self._refresh_preview()
        self._show_view(prev_view)

    def _on_theme_selected(self, selected_theme: str) -> None:
        self.theme_var.set(selected_theme)
        self._apply_theme(selected_theme)
        self._update_settings_summary()
        self._save_settings()

    def _describe_license(self) -> str:
        info = getattr(self, "license_info", {}) or {}
        if info.get("is_valid") and info.get("is_trial"):
            days_remaining = info.get("days_remaining", 0)
            return f"Free trial active. {days_remaining} day(s) remaining before paid activation is required."
        if info.get("is_valid"):
            return "Commercial license active. Full access is unlocked on this device."
        return "Trial expired. Activate with your activation code to continue using MessageCannon."

    def _update_license_ui(self) -> None:
        info = getattr(self, "license_info", {}) or {}
        if info.get("is_valid") and info.get("is_trial"):
            badge_text = f"Trial: {info.get('days_remaining', 0)}d left"
            badge_color = T.BADGE_BG
            badge_text_color = T.TEXT_MUTED
            activate_state = "normal"
            deactivate_state = "disabled"
            card_value = badge_text
        elif info.get("is_valid"):
            badge_text = "Licensed"
            badge_color = T.BADGE_BG
            badge_text_color = T.SUCCESS
            activate_state = "disabled"
            deactivate_state = "normal"
            card_value = "Paid"
        else:
            badge_text = "Activation Required"
            badge_color = T.BG_SURFACE
            badge_text_color = T.DANGER
            activate_state = "normal"
            deactivate_state = "disabled"
            card_value = "Locked"

        self.license_status_var.set(self._describe_license())
        self.license_badge_var.set(badge_text)

        if hasattr(self, "sidebar_license_badge"):
            self.sidebar_license_badge.configure(fg_color=badge_color, text_color=badge_text_color)
        if hasattr(self, "settings_license_chip"):
            self.settings_license_chip.configure(fg_color=badge_color, text_color=badge_text_color)
        if hasattr(self, "dashboard_activate_button"):
            self.dashboard_activate_button.configure(state=activate_state)
        if hasattr(self, "settings_activate_button"):
            self.settings_activate_button.configure(state=activate_state)
        if hasattr(self, "settings_deactivate_button"):
            self.settings_deactivate_button.configure(state=deactivate_state)
        if hasattr(self, "dashboard_cards"):
            self.dashboard_cards["License State"].configure(text=card_value)
        if hasattr(self, "dashboard_card_meta"):
            self.dashboard_card_meta["License State"].configure(text=self._describe_license())

    def _update_compose_summary(self) -> None:
        selected_count = len(self._get_selected_contacts()) if hasattr(self, "compose_contacts_frame") else 0
        # "N selected" alone reads as an eligibility count ("only N of my
        # contacts are usable") rather than what it actually is -- how many
        # checkboxes the user has ticked, starting at 0 by default. Shows
        # the denominator explicitly so "1 selected" can't be misread as
        # "only 1 of my contacts showed up" (real user confusion, live
        # testing) when in fact all contacts render, none are pre-checked.
        available_count = len([c for c in self.contacts if not c.opted_out])
        self.compose_contacts_var.set(f"{selected_count} of {available_count} selected")
        self.compose_delay_var.set(f"{self.delay_var.get()} sec cadence")
        self.compose_limit_var.set(f"Daily cap {self.daily_limit_var.get()}")

    def _update_settings_summary(self) -> None:
        self.settings_delay_chip_var.set(f"Cadence {self.delay_var.get()} sec")
        self.settings_theme_chip_var.set(f"Theme {self.theme_var.get()}")
        guardrails = "Guardrails On" if self.consent_required_var.get() or self.jitter_var.get() else "Guardrails Minimal"
        self.settings_guard_chip_var.set(guardrails)

    def _update_report_summary(self) -> None:
        self.report_export_status_var.set(f"{self.report_format_var.get().upper()} export ready")

    def _update_contacts_summary(self, visible_count: Optional[int] = None, query: Optional[str] = None) -> None:
        total_count = len(self.contacts)
        visible = total_count if visible_count is None else visible_count
        search_query = self.search_var.get().strip() if query is None else query.strip()
        self.contacts_total_var.set(f"{total_count} loaded")
        self.contacts_visible_var.set(f"{visible} visible")
        if search_query:
            self.contacts_search_var.set(f"Filtered by '{search_query}'")
        elif total_count:
            self.contacts_search_var.set("Search by name, phone, or campaign segment")
        else:
            self.contacts_search_var.set("Import contacts to build your outreach directory")

    def _deactivate_license(self) -> None:
        if not messagebox.askyesno(
            "Deactivate License",
            "Deactivate the paid license on this device? The free trial will not be restored.",
        ):
            return

        result = LicenseManager.deactivate_license()
        if not result.get("success"):
            messagebox.showerror("Deactivate Failed", str(result.get("message", "Could not deactivate license.")))
            return

        self.license_info = LicenseManager.check_license()
        self.license_locked = True
        self._update_license_ui()
        self._log_activity("Commercial license deactivated")
        messagebox.showinfo("License Deactivated", "This device now requires activation to continue.")
        self._show_license_gate()

    def _on_delay_change(self, value: float) -> None:
        rounded = int(round(value))
        self.delay_var.set(rounded)
        self.delay_label.configure(text=f"{rounded} sec")
        if hasattr(self, "_compose_delay_slider"):
            self._compose_delay_slider.set(rounded)
            self._compose_delay_label.configure(text=f"{rounded} sec")
            self._update_send_rate_warning()
        self._update_compose_summary()
        self._save_settings()

    def _on_compose_delay_change(self, value: float) -> None:
        rounded = int(round(value))
        self._compose_delay_label.configure(text=f"{rounded} sec")
        self._on_delay_change(value)

    def _update_send_rate_warning(self) -> None:
        if self.delay_var.get() < 15:
            self._send_rate_warning_var.set(
                "⚠ Very short delay increases the risk of your account being flagged — 30s+ is safer.")
        else:
            self._send_rate_warning_var.set("")

    def _on_daily_limit_change(self, value: float) -> None:
        rounded = int(round(value))
        self.daily_limit_var.set(rounded)
        self.limit_label.configure(text=str(rounded))
        self._update_daily_limit_warning()
        self._update_email_warmup_status_label()
        self._update_compose_summary()
        self._save_settings()

    def _email_warmup_remaining_today(self) -> int:
        """How many more emails can be sent today under the warm-up ramp
        (see core/warmup_scheduler.py), already accounting for how many
        were sent earlier today. Never negative."""
        start = warmup_scheduler.parse_date(self._email_warmup_start_date)
        cap = warmup_scheduler.effective_daily_cap(start, date.today(), self.daily_limit_var.get())
        sent_today = self.db.get_email_sent_count_on(warmup_scheduler.format_date(date.today()))
        return max(cap - sent_today, 0)

    def _ensure_email_warmup_started(self) -> None:
        """Called once a real email campaign has actually sent at least one
        message — records today as day 0 of the ramp if warm-up hasn't
        already been started. Never overwrites an existing start date."""
        if self._email_warmup_start_date:
            return
        self._email_warmup_start_date = warmup_scheduler.format_date(date.today())
        self._save_settings()

    def _update_email_warmup_status_label(self) -> None:
        if not hasattr(self, "email_warmup_status_label"):
            return
        start = warmup_scheduler.parse_date(self._email_warmup_start_date)
        text = warmup_scheduler.ramp_status_text(start, date.today(), self.daily_limit_var.get())
        self.email_warmup_status_label.configure(text=text)
        self._update_reputation_indicator()

    def _update_reputation_indicator(self) -> None:
        """"Recommended safe volume today" -- a basic, honest combination of
        the warm-up ramp with any real, recently-logged failure rate. No
        sample data is ever used: with zero send history the recommendation
        is simply the ramp's own conservative default (see
        core/reputation.py)."""
        if not hasattr(self, "reputation_label"):
            return
        start = warmup_scheduler.parse_date(self._email_warmup_start_date)
        since = date.today() - timedelta(days=reputation.RECENT_WINDOW_DAYS)
        stats = self.db.get_email_stats_since(warmup_scheduler.format_date(since))
        signal = reputation.compute_failure_signal(stats)
        rec = reputation.recommended_safe_volume_today(
            start, date.today(), self.daily_limit_var.get(), signal)

        risk_color = {
            "unknown": T.TEXT_MUTED, "low": T.SUCCESS,
            "medium": T.DANGER_ON_BADGE, "high": T.DANGER_ON_BADGE,
        }.get(rec.risk_level, T.TEXT_MUTED)
        self.reputation_label.configure(
            text=f"📊 Recommended safe volume today: {rec.recommended}/day — {rec.reason}",
            text_color=risk_color)

    def _render_whatsapp_accounts(self) -> None:
        """Multi-number groundwork (Item 7, final completion pass) --
        lists configured accounts with a Remove button per row. Each
        account is just a label + an isolated session directory at this
        point (see core/whatsapp_accounts.py); no live session/QR
        initialization happens from this list."""
        if not hasattr(self, "wa_accounts_list_frame"):
            return
        for child in self.wa_accounts_list_frame.winfo_children():
            child.destroy()

        accounts = wa_accounts.list_accounts(self.db)
        if not accounts:
            ctk.CTkLabel(self.wa_accounts_list_frame, text="No additional numbers configured yet.",
                         text_color=T.TEXT_MUTED, font=ctk.CTkFont(size=11)).pack(anchor="w")
            return

        for account in accounts:
            row = ctk.CTkFrame(self.wa_accounts_list_frame, fg_color=T.BADGE_BG, corner_radius=8)
            row.pack(fill="x", pady=3)
            ctk.CTkLabel(row, text=f"📱 {account.label}", text_color=T.TEXT_HEAD,
                         font=ctk.CTkFont(size=12)).pack(side="left", padx=12, pady=8)
            ctk.CTkButton(row, text="Remove", width=80, height=24, corner_radius=6,
                          fg_color=T.DANGER, hover_color=T.DANGER_HOVER, text_color=T.TEXT_HEAD,
                          font=ctk.CTkFont(size=10),
                          command=lambda a=account: self._remove_whatsapp_account(a),
                          ).pack(side="right", padx=12, pady=6)

    def _add_whatsapp_account(self) -> None:
        label = self._wa_new_account_var.get().strip()
        try:
            wa_accounts.add_account(self.db, label)
        except ValueError as exc:
            show_toast(self, str(exc), kind="error")
            return
        self._wa_new_account_var.set("")
        self._render_whatsapp_accounts()
        show_toast(self, f'"{label}" added — configure its own session separately.', kind="success")

    def _remove_whatsapp_account(self, account: wa_accounts.WhatsAppAccount) -> None:
        wa_accounts.remove_account(self.db, account.label)
        self._render_whatsapp_accounts()
        show_toast(self, f'"{account.label}" removed.', kind="success")

    def _update_daily_limit_warning(self) -> None:
        limit = self.daily_limit_var.get()
        if limit > 300:
            self.limit_warning_label.configure(
                text=f"High risk: {limit}/day is well above what unofficial WhatsApp automation "
                     "can sustain without triggering a ban — see the warning in System Experience.")
        elif limit > 50:
            self.limit_warning_label.configure(text="Warning: limits above 50 increase account risk.")
        else:
            self.limit_warning_label.configure(text="")

    def _load_templates(self) -> None:
        records = self.db.get_templates()
        if not records:
            template_path = Path(__file__).resolve().parents[1] / "assets" / "templates" / "default_templates.json"
            if template_path.exists():
                try:
                    items = json.loads(template_path.read_text(encoding="utf-8"))
                    for item in items:
                        self.db.add_template(
                            Template(
                                name=item.get("name", "Template"),
                                category=item.get("category", "General"),
                                message_text=item.get("message", ""),
                                description=item.get("description"),
                                is_default=bool(item.get("is_default", False)),
                            )
                        )
                except Exception as exc:
                    Logger.warning(f"Could not seed templates: {exc}")
        self.templates = self.db.get_templates()
        options = ["Custom Message"] + [template.name for template in self.templates]
        self.template_menu.configure(values=options)
        self.template_var.set(options[0])

    def _reload_contacts(self) -> None:
        self.contacts = self.contact_manager.get_all_contacts()
        self.contacts_summary_label.configure(text=f"{len(self.contacts)} contacts loaded")
        self._update_contacts_summary(len(self.contacts), "")
        self._sync_contact_selection()
        self._render_contacts_directory()
        self._render_compose_contacts()
        self._update_compose_summary()
        self._refresh_preview()
        self._refresh_stats(update_text_feeds=True, update_dashboard_periods=True)
        self._refresh_compose_email_recipients()
        self._refresh_email_preview()

    def _sync_contact_selection(self) -> None:
        valid_keys = set()
        for index, contact in enumerate(self.contacts):
            key = self._contact_key(contact, index)
            valid_keys.add(key)
            if key not in self.contact_selection_vars:
                self.contact_selection_vars[key] = BooleanVar(value=False)
        for key in list(self.contact_selection_vars.keys()):
            if key not in valid_keys:
                del self.contact_selection_vars[key]

    def _on_header_search(self, *_) -> None:
        query = self._header_search_var.get()
        if self._active_view == "Contacts":
            # Item 30 (Final Premium Polish Pass): _show_view() calls this on
            # every single navigation to Contacts, unconditionally -- but
            # every real data mutation (import, per-row delete, opt-out
            # toggle) already calls _render_contacts_directory() directly
            # right after it changes anything (see _reload_contacts,
            # _delete_contact_row, _toggle_contact_opt_out). So re-rendering
            # here too, when the query hasn't actually changed since the
            # directory was last drawn, is pure redundant work -- measured
            # directly at ~1.0-1.3s for this app's real widget-tree size
            # (9 real contacts, confirmed via an isolated timing script, not
            # guessed) for zero visible difference on screen. Skip it.
            if (query == self.search_var.get()
                    and getattr(self, "_contacts_directory_rendered", False)):
                return
            self.search_var.set(query)
            self._schedule_contact_search()
        elif self._active_view == "History":
            self._render_history_rows(query)

    def _schedule_contact_search(self) -> None:
        if self._search_job is not None:
            self.after_cancel(self._search_job)
        self._search_job = self.after(300, self._render_contacts_directory)

    def _render_contacts_directory(self) -> None:
        self._search_job = None
        self._contacts_directory_rendered = True
        for child in self.contacts_directory.winfo_children():
            child.destroy()

        query = self.search_var.get().strip().lower()
        results = [
            contact for contact in self.contacts
            if not query
            or query in contact.phone.lower()
            or query in (contact.name or "").lower()
            or query in (contact.email or "").lower()
        ]
        self._update_contacts_summary(len(results), query)
        if not results:
            empty = ctk.CTkFrame(self.contacts_directory, fg_color=T.BG_INNER,
                                 corner_radius=12, border_width=1, border_color=T.BG_BORDER)
            empty.pack(fill="x", padx=6, pady=6)
            ctk.CTkLabel(empty, text="No contacts found",
                         font=ctk.CTkFont(size=14, weight="bold"),
                         text_color=T.TEXT_HEAD).pack(padx=16, pady=(16, 4), anchor="w")
            ctk.CTkLabel(empty,
                         text="Adjust your search or import a CSV/Excel list to continue.",
                         text_color=T.TEXT_MUTED).pack(padx=16, pady=(0, 16), anchor="w")
            self._bind_scrollable_frame_mousewheel(self.contacts_directory)
            return

        display_limit = 200
        visible = results[:display_limit]
        if len(results) > display_limit:
            notice = ctk.CTkFrame(self.contacts_directory, fg_color=T.BADGE_BG, corner_radius=8)
            notice.pack(fill="x", padx=4, pady=(4, 2))
            ctk.CTkLabel(
                notice,
                text=f"Showing first {display_limit} of {len(results)} matches — refine your search.",
                text_color=T.ACCENT_TEXT, font=ctk.CTkFont(size=11),
            ).pack(padx=10, pady=6, anchor="w")

        for idx, contact in enumerate(visible):
            card = ctk.CTkFrame(self.contacts_directory, fg_color=T.BG_SURFACE,
                                corner_radius=10, border_width=1, border_color=T.BG_BORDER)
            card.pack(fill="x", padx=6, pady=3)
            top = ctk.CTkFrame(card, fg_color="transparent")
            top.pack(fill="x", padx=16, pady=(12, 3))
            ctk.CTkLabel(top, text=contact.name or "Unnamed Contact",
                         font=ctk.CTkFont(size=13, weight="bold"),
                         text_color=T.TEXT_HEAD).pack(anchor="w", side="left")
            # Bounced takes priority over Unsubscribed/Active -- it's a
            # more specific, more actionable signal (a real confirmed
            # delivery failure, not a preference), and a contact can be
            # both bounced and opted-out at once without needing two badges.
            if contact.bounced:
                ctk.CTkLabel(top, text="Bounced",
                             fg_color=T.BADGE_BG, corner_radius=999,
                             padx=8, pady=3,
                             text_color=T.DANGER_ON_BADGE, font=ctk.CTkFont(size=10, weight="bold"),
                             ).pack(anchor="e", side="right")
            elif contact.opted_out:
                ctk.CTkLabel(top, text="Unsubscribed",
                             fg_color=T.BADGE_BG, corner_radius=999,
                             padx=8, pady=3,
                             text_color=T.DANGER_ON_BADGE, font=ctk.CTkFont(size=10, weight="bold"),
                             ).pack(anchor="e", side="right")
            else:
                ctk.CTkLabel(top, text="Active",
                             fg_color=T.BADGE_BG, corner_radius=999,
                             padx=8, pady=3,
                             text_color=T.ACCENT_TEXT, font=ctk.CTkFont(size=10, weight="bold"),
                             ).pack(anchor="e", side="right")
            ctk.CTkLabel(card, text=contact.phone, text_color=T.TEXT_MUTED,
                         font=ctk.CTkFont(size=12)).pack(anchor="w", padx=16, pady=(0, 3))

            if contact.bounced:
                bounce_row = ctk.CTkFrame(card, fg_color="transparent")
                bounce_row.pack(fill="x", padx=16, pady=(0, 3))
                ctk.CTkLabel(bounce_row, text="✉ Email bounced — excluded from future email sends",
                             text_color=T.DANGER_ON_BADGE, font=ctk.CTkFont(size=10, weight="bold"),
                             ).pack(side="left")
                ctk.CTkButton(bounce_row, text="Clear Bounced Flag", width=130, height=22, corner_radius=6,
                              fg_color="transparent", hover_color=T.BG_BORDER,
                              border_width=1, border_color=T.ACCENT, text_color=T.ACCENT_TEXT,
                              font=ctk.CTkFont(size=10),
                              command=lambda c=contact: self._toggle_contact_bounced(c, False),
                              ).pack(side="right")

            footer = ctk.CTkFrame(card, fg_color="transparent")
            footer.pack(fill="x", padx=16, pady=(0, 12))
            ctk.CTkLabel(footer,
                         text=f"ID {contact.id if contact.id is not None else '—'}",
                         text_color=T.TEXT_MUTED, font=ctk.CTkFont(size=11),
                         ).pack(side="left")
            ctk.CTkButton(footer, text="🗑 Delete", width=76, height=22, corner_radius=6,
                          fg_color=T.DANGER, hover_color=T.DANGER_HOVER, text_color=T.TEXT_HEAD,
                          font=ctk.CTkFont(size=10),
                          command=lambda c=contact: self._delete_contact_row(c),
                          ).pack(side="right", padx=(6, 0))
            if contact.opted_out:
                ctk.CTkLabel(footer, text="Excluded from all sends",
                             text_color=T.DANGER_ON_BADGE, font=ctk.CTkFont(size=10, weight="bold"),
                             ).pack(side="left", padx=(10, 0))
                ctk.CTkButton(footer, text="Resubscribe", width=90, height=22, corner_radius=6,
                              fg_color=T.BADGE_BG, hover_color=T.BG_BORDER, text_color=T.ACCENT_TEXT,
                              font=ctk.CTkFont(size=10),
                              command=lambda c=contact: self._toggle_contact_opt_out(c, False),
                              ).pack(side="right")
            else:
                ctk.CTkLabel(footer, text="Ready for campaign",
                             text_color=T.SUCCESS, font=ctk.CTkFont(size=10, weight="bold"),
                             ).pack(side="left", padx=(10, 0))
                ctk.CTkButton(footer, text="Unsubscribe", width=90, height=22, corner_radius=6,
                              fg_color=T.BADGE_BG, hover_color=T.BG_BORDER, text_color=T.DANGER_ON_BADGE,
                              font=ctk.CTkFont(size=10),
                              command=lambda c=contact: self._toggle_contact_opt_out(c, True),
                              ).pack(side="right")

        self._bind_scrollable_frame_mousewheel(self.contacts_directory)

    def _toggle_contact_bounced(self, contact: Contact, bounced: bool) -> None:
        """Manual clear (or, in principle, re-set) of a contact's bounced
        flag -- e.g. after confirming a typo'd address was fixed. Bounced is
        normally set automatically by a real IMAP bounce check, never by
        guessing; this is the escape hatch for a false positive or a
        since-corrected address."""
        if contact.id is None:
            return
        ok = self.db.set_contact_bounced(contact.id, bounced)
        if not ok:
            show_toast(self, "Could not update contact.", kind="error")
            return
        contact.bounced = bounced
        self._log_activity(
            f"{'Marked bounced' if bounced else 'Cleared bounced flag'}: {contact.name or contact.phone}")
        show_toast(
            self,
            f"{contact.name or contact.phone} {'marked as bounced' if bounced else 'bounced flag cleared — eligible for email again'}.",
            kind="success")
        self._render_contacts_directory()
        self._render_compose_contacts()

    def _toggle_contact_opt_out(self, contact: Contact, opted_out: bool) -> None:
        if contact.id is None:
            return
        ok = self.db.set_contact_opted_out(contact.id, opted_out)
        if not ok:
            show_toast(self, "Could not update contact.", kind="error")
            return
        contact.opted_out = opted_out
        self._log_activity(
            f"{'Unsubscribed' if opted_out else 'Resubscribed'}: {contact.name or contact.phone}")
        show_toast(
            self,
            f"{contact.name or contact.phone} {'unsubscribed — excluded from all future sends' if opted_out else 'resubscribed'}.",
            kind="success")
        self._render_contacts_directory()
        self._render_compose_contacts()

    def _delete_contact_row(self, contact: Contact) -> None:
        """Per-row delete from the Contacts directory. A single explicit
        askyesno (same weight as the WhatsApp panel's own Reset Session
        confirm) rather than the Danger Zone's typed-confirmation gate --
        that gate is reserved for irreversible *bulk* operations; a single
        row is a lighter, still-deliberate action, not a one-click accident
        (the button itself requires a click on a labeled Delete button, not
        an ambient control)."""
        if contact.id is None:
            return
        label = contact.name or contact.phone
        if not messagebox.askyesno(
            "Delete Contact",
            f"Permanently delete {label}? This cannot be undone.",
        ):
            return
        ok = self.db.delete_contact(contact.id)
        if not ok:
            show_toast(self, "Could not delete contact.", kind="error")
            return
        self.contacts = [c for c in self.contacts if c.id != contact.id]
        self._log_activity(f"Deleted contact: {label}")
        show_toast(self, f"{label} deleted.", kind="success")
        self._render_contacts_directory()
        self._render_compose_contacts()

    def _render_compose_contacts(self) -> None:
        for child in self.compose_contacts_frame.winfo_children():
            child.destroy()

        if not self.contacts:
            ctk.CTkLabel(self.compose_contacts_frame, text="Import contacts to start composing.", text_color=T.TEXT_MUTED).pack(
                padx=14, pady=14, anchor="w"
            )
            self._bind_scrollable_frame_mousewheel(self.compose_contacts_frame)
            self._sync_widget_theme(self.compose_contacts_frame)
            return

        for index, contact in enumerate(self.contacts):
            key = self._contact_key(contact, index)
            if contact.opted_out:
                self.contact_selection_vars[key].set(False)
                ctk.CTkCheckBox(
                    self.compose_contacts_frame,
                    text=f"{contact.name or 'Unnamed'}  |  {contact.phone}  —  Unsubscribed",
                    variable=self.contact_selection_vars[key],
                    state="disabled",
                    fg_color=T.TEXT_DIM, border_color=T.TEXT_DIM,
                    text_color=T.TEXT_DIM,
                    corner_radius=4,
                ).pack(fill="x", padx=10, pady=6, anchor="w")
                continue
            ctk.CTkCheckBox(
                self.compose_contacts_frame,
                text=f"{contact.name or 'Unnamed'}  |  {contact.phone}",
                variable=self.contact_selection_vars[key],
                command=self._refresh_preview,
                fg_color=T.ACCENT, border_color=T.ACCENT,
                hover_color=T.ACCENT_HOVER, checkmark_color=T.TEXT_HEAD,
                corner_radius=4, text_color=T.TEXT_HEAD,
            ).pack(fill="x", padx=10, pady=6, anchor="w")

        self._bind_scrollable_frame_mousewheel(self.compose_contacts_frame)
        self._sync_widget_theme(self.compose_contacts_frame)

    def _toggle_select_all(self) -> None:
        selected = self.select_all_var.get()
        for index, contact in enumerate(self.contacts):
            if contact.opted_out:
                continue  # never auto-select opted-out contacts
            key = self._contact_key(contact, index)
            variable = self.contact_selection_vars.get(key)
            if variable is not None:
                variable.set(selected)
        self._update_compose_summary()
        self._refresh_preview()

    def _build_insert_variable_menu(self, parent, labels: list, on_pick) -> ctk.CTkOptionMenu:
        """A CTkOptionMenu repurposed as a command menu (Item 9 of the Live
        Testing Findings pass): it always shows the placeholder text rather
        than the last-picked value, since selecting an item here inserts a
        variable at the cursor -- it isn't a persistent setting to remember,
        unlike the real Template dropdown right next to it."""
        placeholder = "Insert variable ▾"
        menu = ctk.CTkOptionMenu(
            parent, values=labels, width=168,
            fg_color=T.BADGE_BG, button_color=T.BADGE_BG, button_hover_color=T.BG_BORDER,
            text_color=T.ACCENT_TEXT, font=ctk.CTkFont(size=11),
            dropdown_fg_color=T.BG_SURFACE, dropdown_hover_color=T.BG_BORDER,
            dropdown_text_color=T.TEXT_HEAD,
        )
        menu.configure(command=lambda label: self._on_insert_variable_picked(menu, placeholder, label, on_pick))
        menu.set(placeholder)
        return menu

    @staticmethod
    def _on_insert_variable_picked(menu: ctk.CTkOptionMenu, placeholder: str, label: str, on_pick) -> None:
        on_pick(label)
        menu.set(placeholder)

    _VARIABLE_LABEL_TOKENS = {
        "Name": "{name}", "Email": "{email}", "Phone": "{phone}",
        "Amount": "{amount}", "Date": "{date}",
    }

    def _insert_variable_label(self, text_widget, label: str) -> None:
        """Inserts the raw {token} for a readable dropdown label (e.g.
        "Name" -> "{name}") at the cursor -- the subsequent on-change
        handler (_on_wa_message_changed / _update_email_warnings) pillifies
        it into a chip immediately after, the same as it would for a
        template/AI-loaded token or one typed by hand."""
        token = self._VARIABLE_LABEL_TOKENS.get(label)
        if not token:
            return
        text_widget.insert("insert", token)
        if text_widget is self.message_textbox:
            self._on_wa_message_changed()
        else:
            self._update_email_warnings()

    def _on_template_selected(self, template_name: str) -> None:
        if template_name == "Custom Message":
            return
        template = next((item for item in self.templates if item.name == template_name), None)
        if template is None:
            return
        self.message_textbox.delete("1.0", "end")
        self.message_textbox.insert("1.0", template.message_text)
        self._on_wa_message_changed()

    def _on_wa_message_changed(self) -> None:
        self._refresh_preview()
        self._pillify_text_widget(self.message_textbox)
        self._update_wa_warning()

    def _make_variable_pill(self, master, token: str) -> ctk.CTkLabel:
        """A small badge-style label standing in for a raw {token} in the
        message editor -- same fg_color/text_color/corner_radius as the
        existing metadata pills (compose_delay_chip etc.), just with
        tighter padding so it sits inline in a text flow instead of a
        standalone row."""
        pill = ctk.CTkLabel(
            master, text=_label_for_variable_token(token), fg_color=T.BADGE_BG,
            text_color=T.ACCENT_TEXT, corner_radius=999, padx=8, pady=0,
            font=ctk.CTkFont(size=11, weight="bold"))
        pill.var_token = token
        return pill

    def _pillify_text_widget(self, text_widget) -> None:
        """Converts any raw {token} substring still present as plain text
        (typed by hand, or just loaded from a template/AI pick/the insert-
        variable dropdown) into an embedded pill widget showing a readable
        label ("Name") instead of raw braces -- Item 9 of the Live Testing
        Findings pass. The underlying stored/sent text is unchanged by this:
        _get_text_with_tokens reconstructs the exact {token} string from
        these pills wherever anything needs to read the real message (see
        that method's own docstring for the full list of call sites that
        must use it instead of a raw .get()).

        CTkTextbox deliberately blocks window_create/dump at its own
        wrapper level (confirmed by reading ctk_textbox.py directly before
        writing this: both raise "embedding widgets is forbidden, would
        probably cause all kinds of problems"), so this operates on the
        real underlying tk.Text (`._textbox` for a CTkTextbox, itself for
        the raw tk.Text email body) the same way the pre-existing
        _highlight_variables/_highlight_variables_tk this replaces already
        did for tag operations.

        Real bug found via direct testing before trusting this (not just
        reading Tk's docs): a first version matched against
        `inner.get("1.0", "end")` and converted the regex's *string*
        offsets straight into "1.0+Nc" Tk indices. That works the first
        time (nothing embedded yet), but `.get()` turns out to silently
        *omit* embedded windows from its returned string entirely -- no
        placeholder character at all, unlike what the Tcl docs' character-
        counting language implies -- so after even one pill already exists,
        every match *after* it in the string is off by one real Tk index
        per pill already in the buffer, corrupting whatever text follows
        (confirmed by reproducing it: typing `{amount}` right after an
        already-pillified `{name}` deleted the wrong characters and left a
        stray brace behind). Fixed by working from `.dump(text=True)`
        instead, which hands back each contiguous *text* segment together
        with its own real starting Tk index -- matching within one
        segment's own local string and offsetting from that segment's own
        real start index is correct regardless of how many pills exist
        anywhere else in the buffer, since dump (unlike get) never merges
        across an embedded window.

        Segments are processed rightmost-first, and matches within each
        segment are also processed rightmost-first, so deleting/replacing
        one match never shifts the real Tk index of a match still to come.
        An already-pillified token is an embedded window, not a text
        segment -- it's simply absent from this dump's text entries, so
        there's no risk of double-conversion or infinite reprocessing on
        every keystroke.
        """
        inner = getattr(text_widget, "_textbox", text_widget)
        segments = [(value, index) for key, value, index in
                    inner.dump("1.0", "end", text=True) if key == "text"]
        for text_value, start_index in reversed(segments):
            for match in reversed(list(re.finditer(r"\{[^{}]+\}", text_value))):
                token = match.group(0)
                start = f"{start_index}+{match.start()}c"
                end = f"{start_index}+{match.end()}c"
                inner.delete(start, end)
                inner.window_create(start, window=self._make_variable_pill(inner, token))

    def _get_text_with_tokens(self, text_widget) -> str:
        """Reads text_widget's content back out as a plain string with real
        {token} substrings restored in place of any embedded variable pills
        -- the canonical way to read a message editor's content now that
        Item 9 can render variables as pills instead of raw text. Every real
        call site that needs the actual message (WhatsApp preview/char-count/
        template-validity checks, email subject/spam checks, save-as-
        template, and both live send paths) must use this instead of a raw
        .get(), or a pillified message would preview/send as literal
        placeholder characters instead of the real {name}-etc tokens
        MessageProcessor.substitute_variables expects."""
        inner = getattr(text_widget, "_textbox", text_widget)
        parts = []
        for key, value, _index in inner.dump("1.0", "end", text=True, window=True):
            if key == "text":
                parts.append(value)
            elif key == "window" and value:
                widget = inner.nametowidget(value)
                parts.append(getattr(widget, "var_token", ""))
        return "".join(parts)

    def _update_wa_warning(self) -> None:
        template = self._get_text_with_tokens(self.message_textbox).strip()
        if not template:
            self._wa_warning_var.set("")
            return
        is_valid, warnings = self.message_processor.validate_template(template)
        if not is_valid:
            self._wa_warning_var.set(f"⚠ {warnings[0]}")
        elif warnings:
            self._wa_warning_var.set(f"ℹ {warnings[0]}")
        else:
            self._wa_warning_var.set(f"{len(template)} characters")

    def _update_email_warnings(self) -> None:
        if not hasattr(self, "_compose_em_body"):
            return
        subject = self._em_subj_var.get()
        if self._compose_card_mode:
            # The locked body isn't the real rich-text content in this mode
            # -- skip pillify/spam-word checks against it (meaningless here)
            # and don't let the rich-text mirror preview clobber the real
            # card preview panel. Subject-length validation still applies —
            # Subject stays editable in this mode.
            warnings = []
            _ok, subj_msg = DataValidator.check_subject_length(subject)
            if subj_msg:
                warnings.append(subj_msg)
            self._em_warning_var.set(
                " · ".join(warnings) if warnings else
                "🔒 Visual HTML card — formatting/spam checks don't apply to card content.")
            return
        self._pillify_text_widget(self._compose_em_body)
        body = self._get_text_with_tokens(self._compose_em_body).strip()
        warnings = []
        _ok, subj_msg = DataValidator.check_subject_length(subject)
        if subj_msg:
            warnings.append(subj_msg)
        spam_hits = DataValidator.check_spam_trigger_words(f"{body} {subject}")
        if spam_hits:
            warnings.append(f"Possible spam words: {', '.join(spam_hits[:3])}")
        self._em_warning_var.set(" · ".join(warnings))
        self._refresh_email_preview()

    # ── Item 10 of the Live Testing Findings pass: rich-text email editor ──

    def _toggle_email_char_tag(self, tag_name: str) -> None:
        """Toggles bold ("b") or italic ("i") across the current selection.
        Pure tag_add/tag_remove -- never touches the underlying text, so any
        embedded variable pill inside the selection is completely
        unaffected (unlike a get/delete/insert round trip, which would
        silently drop it -- see _pillify_text_widget's own docstring for
        why that failure mode is real in this exact widget). Whether to add
        or remove is decided by the tag state of just the first character of
        the selection -- a deliberate, simple approximation consistent with
        this being a scoped "simple" rich-text editor, not a full word
        processor."""
        widget = self._compose_em_body
        if not widget.tag_ranges("sel"):
            return
        already = tag_name in widget.tag_names("sel.first")
        if already:
            widget.tag_remove(tag_name, "sel.first", "sel.last")
        else:
            widget.tag_add(tag_name, "sel.first", "sel.last")
        self._update_email_warnings()

    def _line_bullet_prefix_present(self, widget: tk.Text, lineno: int) -> bool:
        """Whether line `lineno` already starts with a literal "• " marker
        -- dump-based (not .get()) so a variable pill sitting at the very
        start of the line is correctly read as "no bullet here" rather than
        silently mis-detected (.get() omits embedded windows from its
        returned string entirely)."""
        text = ""
        for key, value, _index in widget.dump(f"{lineno}.0", f"{lineno}.0+2c", text=True, window=True):
            if key == "window":
                return False
            if key == "text":
                text += value
        return text == "• "

    def _toggle_email_bullet_list(self) -> None:
        """Toggles a leading "• " on each selected line (or the current
        line with no selection). Only ever inserts/deletes exactly the 2
        literal bullet characters at each line's own start index -- never
        rewrites a line's full content -- so this is safe regardless of
        what pills/formatting exist elsewhere on the line."""
        widget = self._compose_em_body
        if widget.tag_ranges("sel"):
            first_line = int(str(widget.index("sel.first")).split(".")[0])
            last_line = int(str(widget.index("sel.last")).split(".")[0])
        else:
            first_line = last_line = int(str(widget.index("insert")).split(".")[0])
        lines = list(range(first_line, last_line + 1))
        non_empty = [ln for ln in lines
                     if widget.compare(f"{ln}.end", ">", f"{ln}.0")] or lines
        all_bulleted = all(self._line_bullet_prefix_present(widget, ln) for ln in non_empty)
        for ln in non_empty:
            has_bullet = self._line_bullet_prefix_present(widget, ln)
            if all_bulleted and has_bullet:
                widget.delete(f"{ln}.0", f"{ln}.0+2c")
            elif not all_bulleted and not has_bullet:
                widget.insert(f"{ln}.0", "• ")
        self._update_email_warnings()

    def _email_rich_runs(self, widget: tk.Text) -> list:
        """Walks the email body's real Tk buffer (dump-based, the same
        pill-safe technique _get_text_with_tokens/_pillify_text_widget
        already use) into an ordered list of
        ("text"|"pill", value, frozenset({"b","i"})) runs -- the shared
        foundation for both HTML export and the live preview panel."""
        active: set = set()
        runs = []
        buf = ""
        buf_tags: frozenset = frozenset()

        def flush():
            nonlocal buf
            if buf:
                runs.append(("text", buf, buf_tags))
                buf = ""

        for key, value, _index in widget.dump("1.0", "end", text=True, tag=True, window=True):
            if key == "tagon" and value in ("b", "i"):
                flush()
                active.add(value)
                buf_tags = frozenset(active)
            elif key == "tagoff" and value in ("b", "i"):
                flush()
                active.discard(value)
                buf_tags = frozenset(active)
            elif key == "text":
                buf += value
            elif key == "window" and value:
                flush()
                widget_obj = widget.nametowidget(value)
                runs.append(("pill", getattr(widget_obj, "var_token", ""), frozenset(active)))
        flush()
        return runs

    @staticmethod
    def _email_rich_lines(runs: list) -> list:
        """Splits a flat run list at "\\n" boundaries into per-line run
        lists, keeping each run's own tag set intact across the split."""
        lines: list = [[]]
        for kind, value, tags in runs:
            if kind == "pill":
                lines[-1].append(("pill", value, tags))
                continue
            parts = value.split("\n")
            for i, part in enumerate(parts):
                if part:
                    lines[-1].append(("text", part, tags))
                if i != len(parts) - 1:
                    lines.append([])
        return lines

    def _email_rich_export_html(self, widget: tk.Text) -> str:
        """Converts the rich-text editor's real content (bold/italic tags,
        bullet-prefixed lines, embedded variable pills) into an HTML string
        -- the canonical way to read the email body for sending/saving now
        that Item 10 replaced the raw-HTML-visible editor with genuine
        WYSIWYG-lite editing. {token} placeholders are reconstructed from
        pills exactly like _get_text_with_tokens already does for the plain-
        text case."""
        def esc(text: str) -> str:
            return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        def run_html(kind: str, value: str, tags) -> str:
            # A pill's stored var_token is already the full "{name}"-style
            # braced string (see _make_variable_pill/_pillify_text_widget),
            # so it must be used as-is here -- wrapping it in another pair
            # of braces would produce a literal "{{name}}".
            text = value if kind == "pill" else esc(value)
            if "b" in tags:
                text = f"<strong>{text}</strong>"
            if "i" in tags:
                text = f"<em>{text}</em>"
            return text

        lines = self._email_rich_lines(self._email_rich_runs(widget))
        groups: list = []
        current_kind = None
        current_lines: list = []

        def flush_group():
            nonlocal current_kind, current_lines
            if current_lines:
                groups.append((current_kind, current_lines))
            current_kind, current_lines = None, []

        for line_runs in lines:
            # Same "var_token is already braced" note as run_html above.
            plain = "".join(v for _k, v, _t in line_runs)
            if plain.strip() == "":
                flush_group()
                continue
            is_bullet = plain.startswith("• ")
            if is_bullet:
                runs_copy = list(line_runs)
                for i, (k, v, t) in enumerate(runs_copy):
                    if k == "text":
                        v = v[2:] if v.startswith("• ") else v.lstrip("•").lstrip()
                        runs_copy[i] = (k, v, t)
                        break
                line_html = "".join(run_html(k, v, t) for k, v, t in runs_copy)
                kind = "ul"
            else:
                line_html = "".join(run_html(k, v, t) for k, v, t in line_runs)
                kind = "p"
            if current_kind is not None and current_kind != kind:
                flush_group()
            current_kind = kind
            current_lines.append(line_html)
        flush_group()

        parts = []
        for kind, line_list in groups:
            if kind == "ul":
                items = "".join(f"<li>{line}</li>" for line in line_list)
                parts.append(f"<ul>{items}</ul>")
            else:
                parts.append(f"<p>{'<br>'.join(line_list)}</p>")
        return "\n".join(parts) if parts else "<p></p>"

    def _load_html_into_email_editor(self, html: str) -> None:
        """Loads a legacy EMAIL_TEMPLATES HTML string into the rich-text
        editor via _HTMLToRichText -- see that class's own docstring for the
        disclosed visual-fidelity trade-off (gradients/colors/CTA buttons
        can't survive; bold/italic/paragraph/bullet/link-URL structure
        does)."""
        parser = _HTMLToRichText(self._compose_em_body)
        parser.feed(html)
        parser.close()

    def _refresh_email_preview(self) -> None:
        """Email's equivalent of WhatsApp's own live preview panel (Item 10
        of the Live Testing Findings pass) -- substitutes real data from the
        first eligible contact into the actual rich-text content (bold/
        italic/bullets mirrored via the same "b"/"i" tags, not flattened to
        plain text) so what's shown is genuinely how the message will look,
        not just its raw template text."""
        if not hasattr(self, "_em_preview_text"):
            return
        preview = self._em_preview_text
        preview.configure(state="normal")
        preview.delete("1.0", "end")
        contacts = [c for c in self.contacts if c.email and not c.opted_out and not c.bounced]
        if not contacts:
            preview.insert("1.0", "Import a contact with an email address to preview "
                           "personalized output.", ("muted",))
            preview.configure(state="disabled")
            return
        contact = contacts[0]
        vars_map = {
            "name": contact.name, "email": contact.email,
            "phone": contact.phone, "sender": self._em_from_name.get(),
        }
        vars_map.update(contact.custom_fields)

        def sub(text: str) -> str:
            for key, value in vars_map.items():
                text = text.replace(f"{{{key}}}", str(value))
            return text

        subject = sub(self._em_subj_var.get())
        preview.insert("end", f"To: {contact.name or contact.email}\n", ("muted",))
        preview.insert("end", f"Subject: {subject}\n\n", ("muted",))
        for _kind, value, tags in self._email_rich_runs(self._compose_em_body):
            # value is already the braced "{name}"-style token for a pill
            # run (var_token), so sub() alone (no re-wrapping) is correct
            # for both pill and plain-text runs.
            preview.insert("end", sub(value), tuple(tags))
        preview.configure(state="disabled")

    # ── "Send as Visual HTML Card" mode (Card Creator's Insert-into-Compose) ──

    def _strip_html_for_preview(self, html: str) -> str:
        """Cheap, best-effort HTML->plain-text for the pre-send confirmation
        dialog's preview text only (not the real sent content, which stays
        real HTML) -- good enough to show "does this look like the right
        card", not a full renderer."""
        text = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", html)
        text = re.sub(r"(?i)<br\s*/?>", "\n", text)
        text = re.sub(r"(?i)</(p|div|li|h[1-6])>", "\n", text)
        # Same concatenation risk _HTMLToRichText.handle_data fixes for the
        # rich-text importer: sibling inline elements (e.g. price/old-price/
        # discount-badge <span>s) often have zero whitespace between them in
        # the source HTML, relying entirely on CSS margin for visual
        # separation -- a real repro caught this producing "$199 50% OFF"
        # -> "$19950% OFF" here. A blanket space after any other closing tag
        # (block tags above already got a real newline) prevents that.
        text = re.sub(r"(?i)</[a-zA-Z0-9]+>", " ", text)
        text = re.sub(r"<[^>]+>", "", text)
        text = html_module.unescape(text)
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n\s*\n+", "\n\n", text)
        return text.strip()

    def _apply_email_card_mode_ui(self) -> None:
        """(Re)applies the current _compose_card_mode state to the Compose
        Email widgets. Called both when entering/exiting the mode and at
        the end of every _build_compose_view rebuild (e.g. a Warm Ivory
        theme switch rebuilds every widget from scratch, which would
        otherwise silently drop a card that was active before the rebuild
        back into a plain, unlocked rich-text editor)."""
        if not hasattr(self, "_compose_em_body"):
            return
        locked = self._compose_card_mode
        if locked:
            self._compose_em_body.grid_remove()
            self._em_card_lock_frame.grid(row=5, column=0, padx=16, pady=(0, 16), sticky="nsew")
        else:
            self._em_card_lock_frame.grid_remove()
            self._compose_em_body.grid(row=5, column=0, padx=16, pady=(0, 16), sticky="nsew")
        state = "disabled" if locked else "normal"
        for widget in getattr(self, "_em_card_mode_controls", []):
            try:
                widget.configure(state=state)
            except Exception:
                pass
        # "Open in browser" only makes sense for a visual HTML card.
        if hasattr(self, "_em_preview_browser_btn"):
            if locked:
                self._em_preview_browser_btn.grid()
            else:
                self._em_preview_browser_btn.grid_remove()

    def _rendered_email_card_html(self) -> str:
        """The real card HTML with the first eligible contact's data
        substituted (obvious sample values if there are no contacts) — the
        exact bytes a recipient would receive, minus the per-send compliance
        footer. Shared by the in-app preview and the browser preview."""
        contacts = [c for c in self.contacts
                    if c.email and not c.opted_out and not c.bounced]
        if contacts:
            c = contacts[0]
            vars_map = {"name": c.name, "email": c.email, "phone": c.phone,
                        "sender": self._em_from_name.get()}
            vars_map.update(c.custom_fields)
        else:
            vars_map = {"name": "Sample Name", "email": "sample@example.com",
                        "phone": "+10000000000", "sender": self._em_from_name.get()}
        html = self._compose_card_html_template
        for key, value in vars_map.items():
            html = html.replace(f"{{{key}}}", str(value))
        return html

    def _open_email_card_preview_in_browser(self) -> None:
        """Reliable fallback for the in-app preview: writes the real
        rendered card HTML to a temp file and opens it in the system
        browser — a full rendering engine, never a blank/blurred strip."""
        if not (self._compose_card_mode and self._compose_card_html_template):
            return
        import tempfile
        html = self._rendered_email_card_html()
        tmp = tempfile.NamedTemporaryFile(
            delete=False, suffix=".html", mode="w", encoding="utf-8")
        tmp.write(html)
        tmp.close()
        webbrowser.open(f"file://{tmp.name}")

    def _open_subject_optimizer(self) -> None:
        """Item 34 (sub-item 1): suggests 3 alternative subject lines,
        optimized for open rates, from the already-drafted email body."""
        api_key = self._ai_api_key.get()
        if not api_key:
            messagebox.showwarning(
                "AI key required", "Add an AI API key in Settings first (Settings -> AI Cards).")
            return
        if self._compose_card_mode and self._compose_card_html_template:
            body_plain = self._strip_html_for_preview(self._compose_card_html_template)
        else:
            body_plain = self._get_text_with_tokens(self._compose_em_body).strip() if hasattr(
                self, "_compose_em_body") else ""
        if not body_plain:
            messagebox.showwarning("Nothing to optimize", "Write the email body first.")
            return

        self._subject_optimize_btn.configure(state="disabled", text="Optimizing…")
        provider = self._ai_provider.get()

        def worker():
            try:
                variants = ai_service.generate_subject_lines(body_plain, api_key, provider=provider)
            except AIServiceError as ex:
                message = str(ex)
                self.after(0, lambda: self._on_subject_optimize_failed(message))
                return
            self.after(0, lambda: self._show_subject_optimizer_results(variants))

        threading.Thread(target=worker, daemon=True).start()

    def _on_subject_optimize_failed(self, message: str) -> None:
        self._subject_optimize_btn.configure(state="normal", text="✨ Optimize")
        messagebox.showerror("Subject optimization failed", message)

    def _show_subject_optimizer_results(self, variants: list) -> None:
        self._subject_optimize_btn.configure(state="normal", text="✨ Optimize")
        if not variants:
            messagebox.showinfo("No suggestions", "The AI didn't return any subject lines.")
            return
        dlg = ctk.CTkToplevel(self)
        dlg.title("Subject Line Suggestions")
        center_on_parent(dlg, 460, 420, self)
        dlg.resizable(False, False)
        dlg.transient(self)
        dlg.grab_set()
        dlg.configure(fg_color=T.BG_MAIN)
        dlg.bind("<Escape>", lambda _e: dlg.destroy())

        ctk.CTkLabel(dlg, text="Pick a subject line", font=ctk.CTkFont(size=15, weight="bold"),
                     text_color=T.TEXT_HEAD).pack(anchor="w", padx=18, pady=(16, 10))
        for variant in variants:
            card = ctk.CTkFrame(dlg, fg_color=T.BG_SURFACE, corner_radius=10,
                                 border_width=1, border_color=T.BG_BORDER)
            card.pack(fill="x", padx=18, pady=6)
            ctk.CTkLabel(card, text=variant["subject"], text_color=T.TEXT_HEAD,
                         font=ctk.CTkFont(size=12, weight="bold"),
                         wraplength=380, justify="left").pack(anchor="w", padx=12, pady=(10, 2))
            if variant.get("rationale"):
                ctk.CTkLabel(card, text=variant["rationale"], text_color=T.TEXT_MUTED,
                             font=ctk.CTkFont(size=10), wraplength=380, justify="left").pack(
                    anchor="w", padx=12, pady=(0, 6))

            def pick(subject=variant["subject"]) -> None:
                self._em_subj_var.set(subject)
                dlg.destroy()
                show_toast(self, "Subject line applied.", kind="success")

            ctk.CTkButton(card, text="Use this", height=26, fg_color=T.ACCENT,
                          hover_color=T.ACCENT_HOVER, text_color=T.TEXT_HEAD,
                          font=ctk.CTkFont(size=11), command=pick).pack(
                anchor="e", padx=12, pady=(0, 10))
        ctk.CTkButton(dlg, text="Close", fg_color=T.BADGE_BG, hover_color=T.BG_BORDER,
                      text_color=T.TEXT_HEAD, command=dlg.destroy).pack(pady=(4, 16))

    def _import_html_into_compose(self) -> None:
        """Item 33: a direct "Import HTML" entry point inside Compose
        itself (Cards tab has its own equivalent — CardCreatorV2._import_html_file
        — this is the "and/or directly in Compose's Email mode" half of the
        ask). Reuses the exact same core.html_import + _enter_email_card_mode
        pipeline, so an imported file sends for real, personalized
        per-recipient via {variable} tokens, exactly like any other visual
        HTML card — never a new mock send path."""
        path = filedialog.askopenfilename(
            title="Import HTML File",
            filetypes=[("HTML files", "*.html *.htm"), ("All files", "*.*")])
        if not path:
            return
        try:
            result = import_html_file(Path(path))
        except HtmlImportError as exc:
            messagebox.showerror("Import failed", str(exc))
            return
        filename = Path(path).name
        subject = result["subject"] or filename
        self._enter_email_card_mode(result["html"], subject)
        show_toast(self, f"Imported {filename} as a visual HTML card.", kind="success")

    def _enter_email_card_mode(self, html_template: str, subject: str) -> None:
        """Called from Card Creator's "Send as Visual HTML Card" choice:
        locks the rich-text editor and stores the real generated card HTML
        (with {variable} tokens preserved) to be sent as-is, substituted
        per-recipient at send time exactly like any other email template."""
        self._compose_card_html_template = html_template
        self._compose_card_mode = True
        self._apply_email_card_mode_ui()
        if hasattr(self, "_em_validation_label"):
            self._em_validation_label.configure(text="")
        self._em_subj_var.set(subject)
        self._update_email_warnings()
        self._render_email_card_preview()

    def _exit_email_card_mode(self) -> None:
        """Reverses _enter_email_card_mode. As a courtesy (not required —
        the user asked for editing to be locked, not for a dead end), the
        real card HTML is flattened into the rich-text editor via the same
        importer already used for legacy HTML templates, so the user isn't
        left with an empty box if they want to keep editing by hand."""
        html_template = self._compose_card_html_template
        self._compose_card_mode = False
        self._compose_card_html_template = ""
        self._apply_email_card_mode_ui()
        if hasattr(self, "_em_card_preview_host"):
            self._em_card_preview_host.grid_remove()
        if hasattr(self, "_em_preview_text"):
            self._em_preview_text.grid()
        if html_template and hasattr(self, "_compose_em_body"):
            self._compose_em_body.delete("1.0", "end")
            self._load_html_into_email_editor(html_template)
        self._update_email_warnings()

    def _ensure_em_card_html_frame(self) -> bool:
        """Lazily creates the real HTML preview widget on first use — same
        pattern as Card Creator's own _ensure_html_frame, reusing the exact
        same optional dependency rather than a second implementation."""
        if self._em_card_html_frame is not None:
            return True
        if not HAS_HTML_PREVIEW:
            return False
        try:
            from ..ui.card_creator_tab import HtmlFrame
            self._em_card_preview_fallback.pack_forget()
            # tkinterweb's engine does not honor CustomTkinter's widget
            # scaling, so on a HiDPI display the card otherwise renders as a
            # tiny, hard-to-read strip inside a large panel. Match the
            # rendering zoom to the app's own scaling factor so the preview
            # is legible; best-effort — never let this stop the frame being
            # created.
            zoom = 1.0
            try:
                from customtkinter.windows.widgets.scaling.scaling_tracker import ScalingTracker
                zoom = max(1.0, float(ScalingTracker.get_widget_scaling(self._em_card_preview_host)))
            except Exception:
                pass
            try:
                self._em_card_html_frame = HtmlFrame(
                    self._em_card_preview_host, messages_enabled=False, zoom=zoom)
            except TypeError:
                self._em_card_html_frame = HtmlFrame(
                    self._em_card_preview_host, messages_enabled=False)
            self._em_card_html_frame.pack(fill="both", expand=True)
            return True
        except Exception as exc:
            Logger.warning(f"Email card HtmlFrame init failed: {exc}")
            self._em_card_html_frame = None
            return False

    def _render_email_card_preview(self) -> None:
        """Renders the real, visually-complete card HTML (gradients/images/
        CTA button intact) into the locked preview panel, substituted with
        the first eligible real contact's data — the genuine "this is what
        the recipient will see" proof the rich-text mirror preview can't
        give for a card this visually rich."""
        if not hasattr(self, "_em_card_preview_host"):
            return
        if hasattr(self, "_em_preview_text"):
            self._em_preview_text.grid_remove()
        self._em_card_preview_host.grid()
        contacts = [c for c in self.contacts if c.email and not c.opted_out and not c.bounced]
        vars_map = {"name": "", "email": "", "phone": "", "sender": self._em_from_name.get()}
        if contacts:
            contact = contacts[0]
            vars_map = {
                "name": contact.name, "email": contact.email,
                "phone": contact.phone, "sender": self._em_from_name.get(),
            }
            vars_map.update(contact.custom_fields)

        def sub(text: str) -> str:
            for key, value in vars_map.items():
                text = text.replace(f"{{{key}}}", str(value))
            return text

        if hasattr(self, "_em_preview_browser_btn"):
            self._em_preview_browser_btn.grid()

        rendered = sub(self._compose_card_html_template)
        if self._ensure_em_card_html_frame():
            try:
                self._em_card_html_frame.load_html(rendered)
            except Exception as exc:
                Logger.warning(f"Email card preview load_html failed: {exc}")
                self._show_em_card_preview_fallback()
        else:
            # tkinterweb present but the widget couldn't init, OR not
            # installed — either way show the informative label rather than
            # an empty frame that reads as "broken".
            self._show_em_card_preview_fallback()

    def _show_em_card_preview_fallback(self) -> None:
        if not hasattr(self, "_em_card_preview_fallback"):
            return
        self._em_card_preview_fallback.configure(
            text="In-app card preview is unavailable right now — click "
                 "\"↗ Open in browser\" above to see the exact card that "
                 "will be sent, or use \"✉ Send test to myself\".")
        try:
            self._em_card_preview_fallback.pack(fill="both", expand=True, padx=12, pady=24)
        except Exception:
            pass

    def _show_email_recipients_list(self) -> None:
        """Item 10 of the Live Testing Findings pass: makes the "Recipients"
        count clickable/expandable, listing exactly which contacts are
        included instead of leaving the user to guess from a bare number."""
        contacts = [c for c in self.contacts if c.email and not c.opted_out and not c.bounced]
        dlg = ctk.CTkToplevel(self)
        dlg.title("Email Recipients")
        center_on_parent(dlg, 420, 480, self)
        dlg.transient(self)
        dlg.grab_set()
        dlg.configure(fg_color=T.BG_MAIN)
        dlg.bind("<Escape>", lambda _e: dlg.destroy())
        dlg.grid_columnconfigure(0, weight=1)
        dlg.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(dlg, text=f"{len(contacts)} recipient{'s' if len(contacts) != 1 else ''}",
                     font=ctk.CTkFont(size=16, weight="bold"), text_color=T.TEXT_HEAD).grid(
            row=0, column=0, padx=20, pady=(20, 10), sticky="w")

        listing = ctk.CTkScrollableFrame(dlg, fg_color=T.BG_INNER, corner_radius=10)
        listing.grid(row=1, column=0, padx=20, pady=(0, 12), sticky="nsew")
        listing.grid_columnconfigure(0, weight=1)
        if not contacts:
            ctk.CTkLabel(listing, text="No contacts with an email address yet.",
                         text_color=T.TEXT_MUTED, font=ctk.CTkFont(size=12)).grid(
                row=0, column=0, padx=12, pady=12, sticky="w")
        for i, contact in enumerate(contacts):
            row = ctk.CTkFrame(listing, fg_color="transparent")
            row.grid(row=i, column=0, sticky="ew", padx=8, pady=4)
            ctk.CTkLabel(row, text=contact.name or "(no name)", text_color=T.TEXT_HEAD,
                         font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w")
            ctk.CTkLabel(row, text=contact.email, text_color=T.TEXT_MUTED,
                         font=ctk.CTkFont(size=11)).pack(anchor="w")

        ctk.CTkButton(dlg, text="Close", fg_color=T.ACCENT, hover_color=T.ACCENT_HOVER,
                      text_color=T.TEXT_HEAD, command=dlg.destroy).grid(
            row=2, column=0, padx=20, pady=(0, 20))

    def _open_ai_compose(self, channel: str) -> None:
        from .ai_compose_dialog import show_ai_compose_dialog

        def on_pick(text: str, subject: str) -> None:
            if channel == "whatsapp":
                self.message_textbox.delete("1.0", "end")
                self.message_textbox.insert("1.0", text)
                self._on_wa_message_changed()
            else:
                self._compose_em_body.delete("1.0", "end")
                self._compose_em_body.insert("1.0", text)
                if subject:
                    self._em_subj_var.set(subject)
                self._update_email_warnings()

        show_ai_compose_dialog(self, channel, on_pick)

    def _open_save_template(self, channel: str) -> None:
        if channel == "whatsapp":
            text = self._get_text_with_tokens(self.message_textbox).strip()
        else:
            # Preserve any bold/italic/bullet formatting via the rich-text
            # HTML exporter (Item 10 of the Live Testing Findings pass) --
            # a plain-text read would silently drop it from the saved
            # template.
            plain = self._get_text_with_tokens(self._compose_em_body).strip()
            text = self._email_rich_export_html(self._compose_em_body) if plain else ""
        if not text:
            messagebox.showwarning("Nothing to save", "Write a message first.")
            return

        dlg = ctk.CTkToplevel(self)
        dlg.title("Save as Template")
        center_on_parent(dlg, 420, 280, self)
        dlg.resizable(False, False)
        dlg.transient(self)
        dlg.grab_set()
        dlg.configure(fg_color=T.BG_MAIN)
        dlg.bind("<Escape>", lambda _e: dlg.destroy())

        ctk.CTkLabel(dlg, text="Template name", text_color=T.TEXT_HEAD).pack(
            anchor="w", padx=20, pady=(20, 4))
        name_var = StringVar(value="")
        name_entry = ctk.CTkEntry(dlg, textvariable=name_var, fg_color=T.BG_INNER,
                                   border_color=T.BG_BORDER, text_color=T.TEXT_HEAD)
        name_entry.pack(fill="x", padx=20)
        name_entry.focus_set()

        ctk.CTkLabel(dlg, text="Category (optional)", text_color=T.TEXT_HEAD).pack(
            anchor="w", padx=20, pady=(14, 4))
        category_var = StringVar(value=channel.capitalize())
        ctk.CTkEntry(dlg, textvariable=category_var, fg_color=T.BG_INNER, border_color=T.BG_BORDER,
                     text_color=T.TEXT_HEAD).pack(fill="x", padx=20)

        status_var = StringVar(value="")
        ctk.CTkLabel(dlg, textvariable=status_var, text_color=T.DANGER_ON_BADGE,
                     font=ctk.CTkFont(size=11)).pack(anchor="w", padx=20, pady=(6, 0))

        def do_save() -> None:
            name = name_var.get().strip()
            if not name:
                status_var.set("Enter a template name.")
                return
            template_id = self.db.add_template(Template(
                name=name, category=category_var.get().strip(), message_text=text))
            if template_id is None:
                status_var.set("A template with that name may already exist.")
                return
            self._load_templates()
            dlg.destroy()
            show_toast(self, f'Template "{name}" saved.', kind="success")

        ctk.CTkButton(dlg, text="Save Template", fg_color=T.ACCENT, hover_color=T.ACCENT_HOVER,
                      text_color=T.TEXT_HEAD, font=ctk.CTkFont(size=13, weight="bold"),
                      command=do_save).pack(pady=(20, 0))
        name_entry.bind("<Return>", lambda _e: do_save())

    def _refresh_preview(self) -> None:
        template = self._get_text_with_tokens(self.message_textbox).strip() if hasattr(self, "message_textbox") else ""
        contacts = self._get_selected_contacts()[:3]
        self._update_compose_summary()
        if not template:
            preview = "Type a message or load a template to preview personalized output."
        elif not contacts:
            preview = "Select contacts to preview how the message will render."
        else:
            parts = []
            for contact in contacts:
                rendered, _ = self.message_processor.substitute_variables(template, contact)
                parts.append(f"To: {contact.name or contact.phone}\n{rendered}")
            preview = "\n\n---\n\n".join(parts)
        self._replace_text(self.preview_text, preview)

    def _get_selected_contacts(self) -> List[Contact]:
        selected: List[Contact] = []
        for index, contact in enumerate(self.contacts):
            if contact.opted_out:
                continue  # opted-out contacts are never eligible for any future send
            key = self._contact_key(contact, index)
            variable = self.contact_selection_vars.get(key)
            if variable and variable.get():
                selected.append(contact)
        return selected

    def _open_import_review(self) -> None:
        from .contact_import_review import show_contact_import_review
        show_contact_import_review(self)

    def _export_contacts_csv(self) -> None:
        """Export all contacts to CSV."""
        import csv

        path = filedialog.asksaveasfilename(
            title="Export Contacts",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")],
            initialfile="messagecannon_contacts.csv",
        )
        if not path:
            return
        try:
            contacts = self.contact_manager.get_all_contacts()
            with open(path, "w", newline="", encoding="utf-8-sig") as handle:
                writer = csv.DictWriter(handle, fieldnames=["name", "email", "phone", "tags"])
                writer.writeheader()
                for contact in contacts:
                    writer.writerow({
                        "name": contact.name or "",
                        "email": contact.email or "",
                        "phone": contact.phone or "",
                        "tags": contact.tags or "",
                    })
            show_toast(self, f"Exported {len(contacts)} contacts to {os.path.basename(path)}", kind="success")
            self._log_activity(f"Exported {len(contacts)} contacts to CSV")
        except Exception as exc:
            Logger.error(f"Export failed: {exc}")
            messagebox.showerror("Export Failed", str(exc))

    def _refresh_update_badge(self) -> None:
        badge = getattr(self, "sidebar_update_badge", None)
        row = getattr(self, "_update_badge_row", None)
        if badge is None or not badge.winfo_exists():
            return
        if self._update_info is None:
            row.pack_forget()
            self._stop_update_dot_pulse()
            return
        self.update_badge_var.set(f"⬆  Update {self._update_info.tag} available")
        row.pack(side="top", fill="x", pady=(0, 10))
        self._start_update_dot_pulse()

    def _start_update_dot_pulse(self) -> None:
        """JobMind Match's `.sidebar-update-dot` pulses via a CSS opacity
        keyframe (1 -> 0.4 -> 1, 1.8s ease-in-out infinite) -- Tk canvas
        items have no alpha channel, so this simulates the same "breathing"
        attention cue by alternating the dot's fill between T.ACCENT and
        T.BG_MAIN (its own background, i.e. fully faded out) instead, on
        the same ~1.8s period. Idempotent: safe to call again while already
        pulsing (used whenever the badge is re-shown)."""
        if self._update_dot_pulse_after_id is not None:
            return
        dot = getattr(self, "_update_badge_dot", None)
        if dot is None:
            return

        def step(lit: bool) -> None:
            if not dot.winfo_exists():
                self._update_dot_pulse_after_id = None
                return
            try:
                dot.itemconfig(
                    self._update_badge_dot_item,
                    fill=T.resolve(T.ACCENT) if lit else T.resolve(T.BG_MAIN))
            except Exception:
                self._update_dot_pulse_after_id = None
                return
            self._update_dot_pulse_after_id = self.after(900, lambda: step(not lit))

        step(True)

    def _stop_update_dot_pulse(self) -> None:
        if self._update_dot_pulse_after_id is not None:
            try:
                self.after_cancel(self._update_dot_pulse_after_id)
            except Exception:
                pass
            self._update_dot_pulse_after_id = None

    def _start_update_check(self) -> None:
        """Background GitHub Releases check, same off-UI-thread pattern as
        _start_session_bootstrap. Never surfaces a popup on failure — see
        core/update_checker.check_for_update's docstring; the badge simply
        stays hidden if the check fails or no newer release exists."""
        def worker() -> None:
            # TEMP-DEBUG (visual confirmation of the sidebar update badge,
            # requested by the user — revert this block after confirming):
            # set MC_FORCE_UPDATE_BADGE=1 to bypass the real GitHub call and
            # feed a fake "newer version available" result instead.
            if os.environ.get("MC_FORCE_UPDATE_BADGE") == "1":
                info = UpdateInfo(
                    version="9.9.9",
                    tag="v9.9.9",
                    release_notes="TEST ONLY — simulated release for visual confirmation of the sidebar update badge. Not a real release.",
                    release_url="https://github.com/farazgoal-boop/MessageCannon/releases",
                    asset_url=None,
                    asset_name=None,
                )
            else:
                info = check_for_update(APP_VERSION)
            if info is not None:
                self.after(0, lambda: self._on_update_check_result(info))

        threading.Thread(target=worker, daemon=True).start()

    def _on_update_check_result(self, info) -> None:
        self._update_info = info
        self._refresh_update_badge()

    def _show_update_dialog(self) -> None:
        if self._update_info is None:
            return
        show_update_dialog(self, self._update_info, APP_VERSION)

    def _apply_downloaded_update(self, installer_path: str) -> None:
        """Real bug fixed (2026-07-28): this used to launch the installer via
        spawn_detached() immediately, then close -- racing the two. Confirmed
        via a real, controlled reproduction (a genuine v1.3.0 install,
        launched for real, with the real v1.3.1 installer run against it
        while still open) that the silent install genuinely fails outright
        (real Inno Setup exit code 5) when the app it's replacing is still
        running and holding its own .exe open -- and since spawn_detached
        never checked the exit code, that failure was completely invisible:
        the app closed anyway and implied success, leaving the user stuck on
        the old version while believing they'd updated.

        Fix: spawn_update_after_current_process_exits() launches a detached
        helper that waits for THIS process's own PID to fully disappear
        (a real Windows process-wait, not a fixed sleep/guess) before it
        ever runs the installer, structurally eliminating the race. Contacts/
        templates/settings live in %APPDATA%\\MessageCannon Pro (see
        db_manager.py), entirely outside the install directory the installer
        touches, so they are structurally untouched by this.

        2026-08-11: also passes the real installed .exe path (read from the
        registry now, before this process exits) as relaunch_exe_path, so
        the helper reopens the new version automatically once the install
        genuinely succeeds -- the user no longer has to find and relaunch
        it themselves via the Start Menu/Desktop icon.

        2026-08-11 follow-up: a real user reported the relaunch above didn't
        visibly work -- the mechanism itself was confirmed correct (the new
        process really does start), but Windows' anti-focus-stealing
        protection can let a background-launched window open invisibly
        behind whatever else is on screen. `AllowSetForegroundWindow(ASFW_ANY
        = -1)`, called here while this (old) process is still the foreground
        app, grants the *next* SetForegroundWindow call from *any* process
        the right to succeed -- both the new app's own normal startup
        focus_force() (main.py) and the relaunch helper's own explicit
        foreground call (update_checker.py) benefit from this. Best-effort:
        wrapped so a failure here (non-Windows, or the call itself failing)
        can never block the update from proceeding."""
        try:
            if sys.platform == "win32":
                ctypes.windll.user32.AllowSetForegroundWindow(-1)  # ASFW_ANY
        except Exception:
            pass
        try:
            spawn_update_after_current_process_exits(
                installer_path, relaunch_exe_path=get_installed_exe_path())
        except Exception as exc:
            Logger.warning(f"Failed to launch downloaded installer: {exc}")
            show_toast(self, f"Could not start the installer: {exc}", kind="error")
            return
        self._on_close()

    def _start_session_bootstrap(self) -> None:
        """Passive, startup-time reconnect attempt -- Item 31: only launches a
        real browser if a previously-verified, unexpired session actually
        exists. get_session_state() is a pure local file/DB read (no browser
        involved), so this check is free and safe to do unconditionally on
        every launch. A user who has never connected WhatsApp, or whose
        session expired/logged out, gets no Chrome popup at all here --
        connecting is then only ever triggered by an explicit action:
        _connect_whatsapp_now() (the new "Connect WhatsApp" button), the
        Setup Wizard's own WhatsApp step, or WhatsAppSender.send_messages()
        itself when the user actually starts a real send."""
        if self.license_locked:
            return
        if not self.whatsapp_sender.get_session_state().is_active:
            self._set_session_status("Not connected - click \"Connect WhatsApp\" to get started")
            return
        self._run_session_bootstrap_worker()

    def _connect_whatsapp_now(self) -> None:
        """Explicit, user-clicked connect (Item 31) -- always launches the
        real browser regardless of any previously-saved session state, since
        an explicit click is exactly the trigger this item asks for, as
        opposed to _start_session_bootstrap's passive, gated startup
        attempt above."""
        btn = getattr(self, "connect_whatsapp_btn", None)
        if btn is not None:
            btn.configure(state="disabled", text="Connecting…")
        self._run_session_bootstrap_worker(on_done=self._restore_connect_button)

    def _restore_connect_button(self) -> None:
        btn = getattr(self, "connect_whatsapp_btn", None)
        if btn is not None and btn.winfo_exists():
            btn.configure(state="normal", text="🔗 Connect WhatsApp")

    def _run_session_bootstrap_worker(self, on_done=None) -> None:
        def worker() -> None:
            self._set_session_status("Launching WhatsApp session...")
            try:
                state = self.whatsapp_sender.initialize()
                self._set_session_status(state.status_text)
                self._log_activity(state.status_text)
                self.after(0, lambda: self._refresh_stats(update_dashboard_periods=True))
            except Exception as exc:
                Logger.warning(f"Session bootstrap failed: {exc}")
                self._set_session_status("Session expired - please scan QR")
                self._log_activity(f"Session bootstrap failed: {exc}")
            finally:
                if on_done is not None:
                    self.after(0, on_done)

        threading.Thread(target=worker, daemon=True).start()

    def _save_wizard_progress(self, **kwargs) -> None:
        """Update setup-wizard progress fields and persist immediately, so
        progress survives even if the app closes right after a step."""
        for key in ("setup_wizard_completed", "setup_wizard_skipped",
                    "setup_wizard_channels", "setup_wizard_channel_index",
                    "setup_wizard_substep"):
            if key in kwargs:
                setattr(self, key, kwargs[key])
        self._save_settings()

    def _maybe_show_setup_wizard(self) -> None:
        """Auto-open the first-run setup wizard, but only if the user has
        never completed OR explicitly skipped it — skipping must stick."""
        if self.setup_wizard_completed or self.setup_wizard_skipped:
            return
        from .setup_wizard import show_setup_wizard
        show_setup_wizard(self)

    def _reopen_setup_wizard(self) -> None:
        """Explicit re-run, e.g. from a Settings button — always starts
        from Welcome regardless of any saved progress."""
        from .setup_wizard import show_setup_wizard
        show_setup_wizard(self, force_restart=True)

    def _resume_setup_wizard(self) -> None:
        """Reopen from wherever the user left off — used by the Dashboard
        'skipped setup' reminder banner (not a forced restart)."""
        from .setup_wizard import show_setup_wizard
        show_setup_wizard(self)

    def _refresh_setup_banner(self) -> None:
        """Rebuild the Dashboard's 'finish setup' reminder banner. Called at
        Campaigns-view build time and again whenever wizard state changes
        mid-session (e.g. the wizard is closed after Skip), since the view
        itself is only built once at startup."""
        if not hasattr(self, "setup_banner_container"):
            return
        for w in self.setup_banner_container.winfo_children():
            w.destroy()
        if not (self.setup_wizard_skipped and not self.setup_wizard_completed):
            return
        banner = ctk.CTkFrame(self.setup_banner_container, fg_color=T.BADGE_BG, corner_radius=10)
        banner.grid(row=0, column=0, padx=20, pady=(0, 16), sticky="ew")
        banner.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(banner, text="Finish setup to send email or WhatsApp campaigns →",
                     text_color=T.ACCENT_TEXT, font=ctk.CTkFont(size=12, weight="bold")).grid(
            row=0, column=0, padx=14, pady=10, sticky="w")
        ctk.CTkButton(banner, text="Resume setup", width=110, height=28, corner_radius=6,
                      fg_color=T.ACCENT, hover_color=T.ACCENT_HOVER, text_color=T.TEXT_HEAD,
                      font=ctk.CTkFont(size=11), command=self._resume_setup_wizard).grid(
            row=0, column=1, padx=(0, 14), pady=10, sticky="e")

    def _do_reset_session(self) -> None:
        self.whatsapp_sender.reset_session()
        self._set_session_status("Session expired - please scan QR")
        self._log_activity("Saved WhatsApp session cleared")
        show_toast(self, "WhatsApp session cleared.", kind="success")

    def _do_delete_all_contacts(self) -> None:
        count = self.db.delete_all_contacts()
        self._reload_contacts()
        self._log_activity(f"Deleted all {count} contacts")
        show_toast(self, f"Deleted {count} contacts.", kind="success")

    def _do_clear_campaign_history(self) -> None:
        count = self.db.clear_campaign_history()
        self._refresh_stats(update_text_feeds=True, update_dashboard_periods=True)
        if hasattr(self, "_history_scroll"):
            self._history_campaigns = self.db.get_recent_campaigns_summary(limit=100)
            self._render_history_rows()
        self._log_activity(f"Cleared campaign history ({count} rows)")
        show_toast(self, "Campaign history cleared.", kind="success")

    def _start_sending(self) -> None:
        if self.license_locked:
            self._show_license_gate()
            return

        if self.send_thread and self.send_thread.is_alive():
            messagebox.showinfo("Campaign Running", "A send operation is already in progress.")
            return

        selected_contacts = self._get_selected_contacts()
        if not selected_contacts:
            messagebox.showwarning("No Contacts", "Select at least one contact before sending.")
            return

        template = self._get_text_with_tokens(self.message_textbox).strip()
        if not template:
            messagebox.showwarning("Missing Message", "Enter a message before sending.")
            return

        if self.consent_required_var.get() and not self.consent_confirmed_var.get():
            messagebox.showwarning("Consent Required", "Confirm recipient consent before sending.")
            return

        if len(selected_contacts) > self.daily_limit_var.get():
            messagebox.showwarning("Daily Limit", "Selected contacts exceed the configured daily limit.")
            return

        messages = []
        for contact in selected_contacts:
            rendered, _ = self.message_processor.substitute_variables(template, contact)
            messages.append(rendered)

        preview_lines = [
            f"To: {c.name or c.phone}\n{m}"
            for c, m in list(zip(selected_contacts, messages))[:3]
        ]

        from .send_dialogs import show_send_confirmation
        show_send_confirmation(
            self, "whatsapp", len(selected_contacts), self.delay_var.get(), preview_lines,
            on_confirm=lambda: self._execute_whatsapp_send(selected_contacts, messages))

    def _execute_whatsapp_send(self, contacts: List[Contact], messages: List[str]) -> None:
        """Real send for a specific (contacts, messages) pair — used both for
        the initial campaign and for "Retry Failed Only" with a subset."""
        self._send_failed_details: List[tuple] = []   # (label, reason) for the report dialog
        self._send_failed_pairs: List[tuple] = []      # (Contact, message) for retry
        self._send_start_time = time.time()

        contacts_by_phone = {c.phone: c for c in contacts}
        messages_by_phone = dict(zip((c.phone for c in contacts), messages))

        self.compose_progress.set(0)
        self.progress_status_var.set("Preparing campaign...")
        self._log_activity(f"Campaign queued for {len(contacts)} contacts")

        def on_event(kind: str, payload: Dict[str, object]) -> None:
            if kind == "message" and payload.get("status") == "failed":
                phone = str(payload.get("phone", ""))
                contact = contacts_by_phone.get(phone)
                label = (contact.name if contact and contact.name else phone) or "Unknown"
                reason = str(payload.get("error") or "Unknown error")
                self._send_failed_details.append((label, reason))
                if contact is not None:
                    self._send_failed_pairs.append((contact, messages_by_phone.get(phone, "")))
            self._handle_sender_event(kind, payload)

        def worker() -> None:
            try:
                result = self.whatsapp_sender.send_messages(
                    contacts=contacts,
                    messages=messages,
                    delay=self.delay_var.get(),
                    use_jitter=self.jitter_var.get(),
                    max_messages=self.daily_limit_var.get(),
                    progress_callback=self._handle_send_progress,
                    event_callback=on_event,
                )
                sent = result.get("sent", 0)
                failed = result.get("failed", 0)
                self.after(0, lambda: self.progress_status_var.set(f"Completed: {sent} sent, {failed} failed"))
                self._log_activity(f"Campaign completed with {sent} sent and {failed} failed")
                self.after(0, lambda: self._show_whatsapp_report(sent, failed))
            except Exception as exc:
                Logger.error(f"Campaign send failed: {exc}")
                self.after(0, lambda: self.progress_status_var.set("Campaign failed"))
                self._log_activity(f"Campaign failed: {exc}")
            finally:
                self.after(0, lambda: self._refresh_stats(update_dashboard_periods=True))

        self.send_thread = threading.Thread(target=worker, daemon=True)
        self.send_thread.start()

    def _show_whatsapp_report(self, sent: int, failed: int) -> None:
        from .send_dialogs import show_send_report
        failed_pairs = list(getattr(self, "_send_failed_pairs", []))
        failed_details = list(getattr(self, "_send_failed_details", []))

        def retry_failed() -> None:
            self._execute_whatsapp_send([c for c, _m in failed_pairs], [m for _c, m in failed_pairs])

        def ai_summary(dialog_callback) -> None:
            self._request_ai_campaign_summary(
                campaign_name=f"WhatsApp {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                sent=sent, failed=failed, bounced=0, dialog_callback=dialog_callback)

        show_send_report(
            self, "whatsapp", sent, failed, failed_details,
            on_retry_failed=retry_failed if failed_pairs else None,
            on_export=self._export_report,
            on_ai_summary=ai_summary,
        )

    def _toggle_pause(self) -> None:
        if self._compose_channel_var.get() == "Email":
            if self._em_pause_event.is_set():
                self._em_pause_event.clear()
                self.progress_status_var.set("Paused")
                self._log_activity("Email campaign paused")
            else:
                self._em_pause_event.set()
                self.progress_status_var.set("Resumed")
                self._log_activity("Email campaign resumed")
            return
        status = self.whatsapp_sender.get_status()
        if not status.get("is_sending"):
            return
        if status.get("is_paused"):
            self.whatsapp_sender.resume_sending()
            self.progress_status_var.set("Resumed")
            self._log_activity("Campaign resumed")
        else:
            self.whatsapp_sender.pause_sending()
            self.progress_status_var.set("Paused")
            self._log_activity("Campaign paused")

    def _stop_sending(self) -> None:
        self.whatsapp_sender.stop_sending()
        self.progress_status_var.set("Stopping...")
        self._log_activity("Campaign stop requested")

    def _handle_send_progress(self, current: int, total: int, status_text: str) -> None:
        self.after(0, lambda: self._update_send_progress(current, total, status_text))

    def _update_send_progress(self, current: int, total: int, status_text: str) -> None:
        from .send_dialogs import format_eta
        self.compose_progress.set(current / total if total else 0)
        failed_count = len(getattr(self, "_send_failed_details", []))
        sent_count = max(0, current - failed_count)
        elapsed = time.time() - getattr(self, "_send_start_time", time.time())
        avg_per_item = (elapsed / current) if current else float(self.delay_var.get())
        eta = max(0, total - current) * avg_per_item
        self.progress_status_var.set(
            f"{sent_count} sent · {failed_count} failed · {format_eta(eta)} remaining ({current}/{total})")

    def _handle_sender_event(self, event_type: str, payload: Dict[str, object]) -> None:
        self.after(0, lambda: self._apply_sender_event(event_type, payload))

    def _apply_sender_event(self, event_type: str, payload: Dict[str, object]) -> None:
        if event_type == "session":
            self._set_session_status(str(payload.get("status", "Session expired - please scan QR")))
            return
        phone = str(payload.get("phone", ""))
        status = str(payload.get("status", "unknown"))
        if phone:
            self._log_activity(f"{phone}: {status}")

    def _refresh_stats(
        self,
        *,
        update_chart: bool = False,
        update_text_feeds: bool = False,
        update_dashboard_periods: bool = False,
    ) -> None:
        stats = self.whatsapp_sender.get_delivery_stats()
        sent_count = int(stats.get("sent_count", 0))
        delivered_count = int(stats.get("delivered_count", 0))
        read_count = int(stats.get("read_count", 0))
        failed_count = int(stats.get("failed_count", 0))
        delivery_rate = float(stats.get("delivery_rate", 0.0))

        self.sent_count_var.set(str(sent_count))
        self.delivered_count_var.set(str(delivered_count))
        self.read_count_var.set(str(read_count))
        self.failed_count_var.set(str(failed_count))
        self.delivery_rate_var.set(f"{delivery_rate:.1f}%")
        if hasattr(self, "delivery_progress"):
            self.delivery_progress.set(min(max(delivery_rate / 100.0, 0.0), 1.0))
        self.reports_feed_var.set(
            f"{sent_count} sent, {delivered_count} delivered, {read_count} read, {failed_count} failed"
        )
        self._update_report_summary()

        if update_dashboard_periods:
            session_state = self.whatsapp_sender.get_session_state()
            today_stats = self.db.get_message_stats_for_period("today")
            week_stats = self.db.get_message_stats_for_period("week")
            month_stats = self.db.get_message_stats_for_period("month")

            # Item 37 (UI/UX benchmark pass): real, pre-existing mismatch
            # found while adding the sparkline below -- this card's own
            # visible label reads "Sent this week" but was populated from
            # `today_stats`, not `week_stats`. Fixed to match its label.
            self.dashboard_cards["Sent Today"].configure(text=str(week_stats.get("sent_count", 0)))
            self.dashboard_cards["Delivery Rate"].configure(text=str(delivered_count))
            self.dashboard_cards["Active Session"].configure(text="Active" if session_state.is_active else "Scan QR")
            # Real bug found while verifying this pass: a theme switch that
            # triggers _rebuild_ui_for_theme (e.g. entering/leaving Warm
            # Ivory) destroys and recreates the whole sidebar+content tree,
            # but _on_theme_selected's own _save_settings() -> _refresh_stats()
            # call can run against a canvas reference that's already been
            # destroyed (or not yet rebuilt) depending on exactly where in
            # that sequence this fires -- a plain hasattr() check isn't
            # enough since the attribute itself survives, only the real Tk
            # widget it points to doesn't. winfo_exists() is the real check.
            if hasattr(self, "dashboard_sparkline") and self.dashboard_sparkline.winfo_exists():
                self._draw_dashboard_sparkline()
            self.dashboard_card_meta["Sent Today"].configure(
                text=f"Today: {today_stats.get('sent_count', 0)} · Month: {month_stats.get('sent_count', 0)}"
            )
            self.dashboard_card_meta["Delivery Rate"].configure(
                text=f"Rate {delivery_rate:.1f}% · Read {read_count}"
            )
            self.dashboard_card_meta["Active Session"].configure(text=session_state.status_text)
            self._update_license_ui()
            self._set_session_status(session_state.status_text)

        if update_text_feeds:
            self.activity_summary_var.set(f"{min(len(self.activity_items), 20)} recent events")
            recent_messages = self.whatsapp_sender.get_recent_activity(limit=12)
            rows = [
                f"[{str(row.get('status', 'unknown')).upper():<10}] {row.get('phone')}   #{row.get('id')}   {row.get('sent_at') or row.get('created_at')}"
                for row in recent_messages
            ]
            if hasattr(self, "reports_text"):
                self._replace_text(self.reports_text, "\n".join(rows) if rows else "No tracked messages yet.")
            self._replace_text(self.activity_text, "\n".join(self.activity_items[:20]) if self.activity_items else "No activity yet.")

        if update_chart and self._active_view == "Reports" and self._reports_chart is not None:
            unread_count = sent_count - read_count if sent_count >= read_count else 0
            self._reports_chart.update(read_count, unread_count)

    def _draw_dashboard_sparkline(self) -> None:
        """Item 37 (UI/UX benchmark pass): a real 7-day send-volume trend
        line on the primary Campaigns dashboard stat card, hand-painted on
        a plain tk.Canvas (same lightweight, dependency-free technique
        already used elsewhere in this app for small inline visuals, e.g.
        _draw_nav_accent and the Card Creator template-gallery thumbnails)
        rather than pulling in a full matplotlib figure for something this
        small. Real, already-logged data only (db.get_daily_sent_counts) --
        never a decorative fake trend."""
        canvas = self.dashboard_sparkline
        # Real bug found and fixed while verifying this pass -- the exact
        # same class of bug this file's own "In-app update checker" section
        # already documents once for _draw_nav_accent's canvas: an
        # update_idletasks() call here flushes Tk's ENTIRE pending idle-
        # callback queue, not just this canvas -- which can include a
        # still-pending, after_idle-deferred
        # _rebuild_ui_for_theme_and_hide_overlay() call (entering/leaving
        # Warm Ivory), running that whole rebuild-and-hide-the-overlay
        # sequence early, synchronously, from deep inside this unrelated
        # method (confirmed directly: caused test_theme_switch_overlay.py's
        # own overlay-stays-mapped assertion to fail, since the overlay got
        # hidden here instead of on its own intended later tick). Fixed the
        # same way that earlier bug was: dropped the forced flush entirely
        # -- winfo_width() alone still returns the real current width once
        # the canvas has been mapped at least once (which it always has by
        # the time _refresh_stats runs), with the existing max(..., 40)
        # fallback covering the one-time not-yet-realized case. A broad
        # try/except still wraps every real Tcl call below regardless, for
        # the same general widget-lifecycle-race reasons already documented
        # elsewhere in this app (e.g. _on_bounce_check_result).
        try:
            canvas.delete("all")
            width = max(canvas.winfo_width(), 40)
            height = 28
            values = self.db.get_daily_sent_counts(days=7)
            max_value = max(values) if any(values) else 1
            pad = 4
            usable_w = width - 2 * pad
            usable_h = height - 2 * pad
            n = len(values)
            step = usable_w / max(n - 1, 1)

            points = []
            for i, value in enumerate(values):
                x = pad + i * step
                y = pad + usable_h - (value / max_value) * usable_h
                points.append((x, y))

            line_color = T.resolve(T.ACCENT)
            fill_color = T.resolve(T.BADGE_BG)

            if len(points) >= 2:
                fill_points = list(points) + [(points[-1][0], height), (points[0][0], height)]
                canvas.create_polygon(
                    [coord for point in fill_points for coord in point],
                    fill=fill_color, outline="")
                canvas.create_line(
                    [coord for point in points for coord in point],
                    fill=line_color, width=2, smooth=True, capstyle="round", joinstyle="round")
            for x, y in points:
                canvas.create_oval(x - 2, y - 2, x + 2, y + 2, fill=line_color, outline="")
        except tk.TclError:
            return

    def _update_reports_chart(self, read_count: int, unread_count: int) -> None:
        """Legacy hook — delegates to reusable chart instance."""
        if self._reports_chart is not None:
            self._reports_chart.update(read_count, unread_count)

    def _export_report(self) -> None:
        try:
            output_path = self.whatsapp_sender.export_report(self.report_format_var.get())
            self._log_activity(f"Report exported to {output_path.name}")
            messagebox.showinfo("Report Exported", f"Saved report to:\n{output_path}")
            self._refresh_stats(update_chart=True, update_text_feeds=True, update_dashboard_periods=True)
        except Exception as exc:
            Logger.error(f"Export failed: {exc}")
            messagebox.showerror("Export Failed", str(exc))

    def _log_activity(self, message: str) -> None:
        entry = f"[{datetime.now().strftime('%H:%M:%S')}] {message}"
        self.activity_items.insert(0, entry)
        self.activity_items = self.activity_items[:50]
        self.activity_summary_var.set(f"{min(len(self.activity_items), 20)} recent events")
        self._replace_text(self.activity_text, "\n".join(self.activity_items[:20]))

    def _set_session_status(self, message: str) -> None:
        self.after(0, lambda: self.session_status_var.set(message))

    def _replace_text(self, widget: ctk.CTkTextbox, value: str) -> None:
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", value)
        widget.configure(state="disabled")

    def _contact_key(self, contact: Contact, index: int) -> str:
        return str(contact.id if contact.id is not None else f"idx-{index}-{contact.phone}")

    def _prewarm_heavy_views(self) -> None:
        """Pay Cards' first-render layout cost here, hidden behind the
        startup splash, instead of on the user's first real click — same
        idea as Compose's synchronous pre-warm in _create_ui(), just
        scheduled 1000ms out so card_creator_tab.py's own
        `self.after(800, self._schedule_preview)` has already populated the
        live preview with real content by the time this runs (warming it
        any earlier measured as a 0-cost no-op against an empty shell)."""
        cards_container = self.view_containers.get("Cards")
        if cards_container is not None:
            cards_container.grid()
            cards_container.update_idletasks()
            cards_container.grid_remove()

    def _periodic_refresh(self) -> None:
        if self._refresh_job is not None:
            self.after_cancel(self._refresh_job)
        try:
            if self._active_view == "Reports":
                self._refresh_stats(update_chart=True, update_text_feeds=True)
            elif self._active_view == "Dashboard":
                self._refresh_stats(update_dashboard_periods=True, update_text_feeds=True)
            else:
                self._refresh_stats()
        finally:
            self._refresh_job = self.after(10000, self._periodic_refresh)

    def _heartbeat_check(self) -> None:
        now = time.time()
        elapsed = now - self._last_heartbeat
        if elapsed > 5.0:
            Logger.warning(f"UI heartbeat delay detected: {elapsed:.1f}s since last tick")
        self._last_heartbeat = now
        self.after(2000, self._heartbeat_check)

    def _on_close(self) -> None:
        # Prevent double-close while shutdown is in progress
        self.protocol("WM_DELETE_WINDOW", lambda: None)

        # Instant visual feedback: hide the window right away. Root cause of the
        # perceived close delay is whatsapp_sender.shutdown() blocking on
        # driver_lock if a Chrome session-bootstrap attempt is still in flight —
        # that lock wait is unavoidable (we must not orphan a Chrome process),
        # but the user doesn't need to see the window sitting there while it
        # resolves. Actual process teardown still happens below, safely.
        try:
            self.withdraw()
        except Exception:
            pass

        # Tour Mode (Item 39 v2) owns several always-on-top overlay
        # Toplevels (ring/card/glow/HUD) plus repeating after()-scheduled
        # animation loops -- left active, those would keep floating on
        # screen after the main window itself is withdrawn, and their
        # after() callbacks would keep firing against a closing window.
        try:
            self.tour_mode.disable()
        except Exception:
            pass

        # Signal active send threads to stop
        self._em_stop_flag.set()
        try:
            self._stop_sending()
        except Exception:
            pass

        def _do_shutdown() -> None:
            try:
                self.whatsapp_sender.shutdown()
            except Exception:
                pass
            self.after(0, self._safe_destroy)

        threading.Thread(target=_do_shutdown, daemon=True).start()

        # Hard deadline: force-destroy after 4 s regardless of shutdown state
        self.after(4000, self._safe_destroy)

    def _safe_destroy(self) -> None:
        try:
            if self.winfo_exists():
                self.destroy()
        except Exception:
            pass
