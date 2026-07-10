"""Modern CustomTkinter main window for MessageCannon."""

from __future__ import annotations

import json
import os
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from tkinter import BooleanVar, IntVar, StringVar, filedialog, messagebox
from typing import Dict, List, Optional

import smtplib
import ssl
import tkinter as tk
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import customtkinter as ctk
from PIL import Image
from ..ui.card_creator_tab import build_card_creator_view
from ..ui.reports_chart import ReportsChart


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

from ..core.contact_manager import ContactManager
from ..core.message_processor import MessageProcessor
from ..core.whatsapp_sender import WhatsAppSender
from ..database.db_manager import DatabaseManager
from ..models import Contact, Template, Campaign, MessageLog, MessageStatus
from ..utils.constants import APP_NAME, APP_VERSION, WINDOW_HEIGHT, WINDOW_WIDTH
from . import theme as T
from ..core import ai_service
from ..core.ai_service import AIServiceError
from ..utils.crypto import encrypt_secret, decrypt_secret
from ..utils.license_manager import LicenseManager
from ..utils.logger import Logger


EMAIL_TEMPLATES = {
    "(none)": ("", ""),
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
    ),
}


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

        self.db = DatabaseManager()
        self.contact_manager = ContactManager()
        self.message_processor = MessageProcessor()
        self.whatsapp_sender = WhatsAppSender()

        self.contacts: List[Contact] = []
        self.templates: List[Template] = []
        self.contact_selection_vars: Dict[str, BooleanVar] = {}
        self.sidebar_buttons: Dict[str, ctk.CTkButton] = {}
        self.sidebar_accent_bars: Dict[str, ctk.CTkFrame] = {}
        self.sidebar_btn_frames: Dict[str, tk.Frame] = {}
        self.view_frames: Dict[str, ctk.CTkFrame] = {}
        self.view_containers: Dict[str, object] = {}
        self.activity_items: List[str] = []
        self.send_thread: Optional[threading.Thread] = None
        self._em_send_thread: Optional[threading.Thread] = None
        self.license_dialog: Optional[ctk.CTkToplevel] = None
        self.license_locked = False
        self._active_view = "Campaigns"
        self._refresh_job: Optional[str] = None
        self._search_job: Optional[str] = None
        self._reports_chart: Optional[ReportsChart] = None
        self._last_heartbeat = time.time()
        self.brand_logo = self._load_brand_image((58, 58))
        self.header_brand_logo = self._load_brand_image((34, 34))

        self.theme_var = StringVar(value="Dark")
        self.delay_var = IntVar(value=30)
        self.daily_limit_var = IntVar(value=50)
        self.jitter_var = BooleanVar(value=True)
        self.consent_required_var = BooleanVar(value=True)
        self.consent_confirmed_var = BooleanVar(value=False)
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
        self._ai_key_visible   = BooleanVar(value=False)
        self._ai_key_status_var = StringVar(value="No API key saved")
        self._em_stop_flag = threading.Event()
        self._em_contacts_list: list = []
        self._em_count_var = StringVar(value="No email contacts imported")
        self._em_compose_count_var = StringVar(value="0 contacts with email")

        self.title(f"{APP_NAME} v{APP_VERSION}")
        self.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.minsize(1220, 760)
        self.configure(fg_color=T.BG_MAIN)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self._load_settings()
        self._apply_theme(self.theme_var.get())
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        self._create_ui()
        self._sync_theme_overrides()
        self._enforce_license()
        self._load_templates()
        self._reload_contacts()
        self._refresh_stats(update_text_feeds=True, update_dashboard_periods=True)
        self._refresh_preview()
        self._show_view("Campaigns")

        self.after(800, self._start_session_bootstrap)
        self.after(900, self._maybe_show_setup_wizard)
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
                bar.configure(bg=T.resolve(T.ACCENT if name == active_view else T.BG_MAIN))
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

    def _create_ui(self) -> None:
        # ── SIDEBAR — uses pack() internally to avoid CTkFrame grid row bugs ──
        self.grid_columnconfigure(0, minsize=220)
        self.sidebar = ctk.CTkFrame(self, corner_radius=0, fg_color=T.BG_MAIN)
        self.sidebar.grid(row=0, column=0, sticky="nsew")

        # ── Brand (packed top) ────────────────────────────────────────────────
        brand_panel = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        brand_panel.pack(side="top", fill="x", padx=16, pady=(18, 12))
        brand_panel.grid_columnconfigure(1, weight=1)
        if self.brand_logo is not None:
            ctk.CTkLabel(brand_panel, text="", image=self.brand_logo).grid(
                row=0, column=0, rowspan=2, padx=(0, 10), sticky="w")
        ctk.CTkLabel(brand_panel, text="MessageCannon",
                     font=ctk.CTkFont(size=14, weight="bold"),
                     text_color=T.TEXT_HEAD).grid(row=0, column=1, sticky="w")
        ctk.CTkLabel(brand_panel, text="Pro  |  Campaign Suite",
                     text_color=T.ACCENT, font=ctk.CTkFont(size=10, weight="bold"),
                     ).grid(row=1, column=1, sticky="w")

        ctk.CTkFrame(self.sidebar, height=1, fg_color=T.BG_BORDER, corner_radius=0
                     ).pack(side="top", fill="x")

        # ── Bottom widgets (packed bottom first so nav fills remaining space) ──
        _bot = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        _bot.pack(side="bottom", fill="x")

        self.sidebar_license_badge = ctk.CTkLabel(
            _bot, textvariable=self.license_badge_var,
            fg_color=T.BADGE_BG, corner_radius=999,
            padx=12, pady=5, text_color=T.SUCCESS,
            font=ctk.CTkFont(size=11, weight="bold"),
        )
        self.sidebar_license_badge.pack(side="bottom", anchor="w", padx=12, pady=(0, 14))

        ctk.CTkButton(
            _bot, text="Reset Session", height=30, corner_radius=6,
            fg_color=T.DANGER, hover_color=T.DANGER_HOVER,
            text_color=T.TEXT_HEAD, font=ctk.CTkFont(size=11),
            command=self._reset_session,
        ).pack(side="bottom", fill="x", padx=10, pady=(0, 6))

        ctk.CTkLabel(_bot, textvariable=self.session_status_var,
                     wraplength=190, justify="left",
                     text_color=T.TEXT_MUTED, font=ctk.CTkFont(size=11),
                     ).pack(side="bottom", fill="x", padx=12, pady=(4, 3))

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

        ctk.CTkFrame(_bot, height=1, fg_color=T.BG_BORDER, corner_radius=0
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

            accent_bar = tk.Frame(btn_frame, width=4, bg=T.resolve(T.BG_MAIN))
            accent_bar.pack(side="left", fill="y", padx=(0, 4))

            button = ctk.CTkButton(
                btn_frame,
                text=f"{icon}  {label}",
                anchor="w",
                height=40,
                corner_radius=8,
                fg_color=T.NAV_INACTIVE,
                hover_color=T.BG_SURFACE,
                border_width=0,
                text_color=T.TEXT_HEAD,
                font=ctk.CTkFont(size=13),
                command=lambda name=view_name: self._show_view(name),
            )
            button.pack(side="left", fill="x", expand=True)

            self.sidebar_buttons[view_name] = button
            self.sidebar_accent_bars[view_name] = accent_bar
            self.sidebar_btn_frames[view_name] = btn_frame

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
            text_color=T.ACCENT,
            font=ctk.CTkFont(size=14),
            command=lambda: self._show_view("Settings"),
        ).pack(side="left", padx=3)

        self.header_pill = ctk.CTkLabel(
            header_right,
            textvariable=self.header_badge_var,
            fg_color=T.BADGE_BG,
            corner_radius=999,
            padx=12,
            pady=5,
            text_color=T.ACCENT,
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

        self.bind("<Control-n>", lambda _event: self._show_view("Compose"))
        self.bind("<Control-i>", lambda _event: self._import_contacts())
        self.bind("<Control-g>", lambda _event: self._show_view("Cards"))

    def _enforce_license(self) -> None:
        """Allow the free trial, then require a paid passkey after expiry."""
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
        dialog.geometry("720x520")
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
                text_color=T.ACCENT, font=ctk.CTkFont(size=11),
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
                         text_color=T.ACCENT).pack(anchor="w", padx=12, pady=(0, 12))

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
            text="Enter your paid passkey below. Activation is stored locally on this device.",
            wraplength=240,
            justify="left",
            text_color=T.TEXT_MUTED,
            font=ctk.CTkFont(size=12),
        ).grid(row=1, column=0, padx=16, pady=(0, 12), sticky="w")

        ctk.CTkLabel(
            right_panel,
            text="If you close the app without activating, the workspace remains locked until a valid passkey is entered.",
            wraplength=240,
            justify="left",
            text_color=T.ACCENT,
            font=ctk.CTkFont(size=11),
        ).grid(row=2, column=0, padx=16, pady=(0, 16), sticky="w")

        self.license_entry = ctk.CTkEntry(
            right_panel,
            placeholder_text="Enter paid passkey",
            height=44,
            border_width=1,
            corner_radius=8,
            fg_color=T.BG_SURFACE,
            border_color=T.BG_BORDER,
            text_color=T.TEXT_HEAD,
        )
        self.license_entry.grid(row=3, column=0, padx=24, pady=(0, 8), sticky="ew")
        self.license_entry.bind("<Return>", lambda _event: self._submit_license_activation())

        ctk.CTkLabel(
            right_panel,
            textvariable=self.license_message_var,
            text_color=T.DANGER,
            wraplength=240,
            justify="left",
        ).grid(row=4, column=0, padx=24, pady=(0, 12), sticky="w")

        secure_note = ctk.CTkFrame(right_panel, fg_color=T.BADGE_BG, corner_radius=12,
                                   border_width=1, border_color=T.BG_BORDER)
        secure_note.grid(row=5, column=0, padx=24, pady=(0, 14), sticky="ew")
        ctk.CTkLabel(
            secure_note,
            text="Secure local activation",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=T.ACCENT,
        ).pack(anchor="w", padx=14, pady=(12, 4))
        ctk.CTkLabel(
            secure_note,
            text="The passkey is validated inside the app and stored only as local license state on this machine.",
            justify="left",
            wraplength=220,
            text_color=T.TEXT_MUTED,
        ).pack(anchor="w", padx=14, pady=(0, 12))

        actions = ctk.CTkFrame(right_panel, fg_color="transparent")
        actions.grid(row=6, column=0, padx=24, pady=(6, 20), sticky="ew")
        actions.grid_columnconfigure(0, weight=1)

        ctk.CTkButton(
            actions,
            text="Exit App",
            fg_color=T.DANGER, hover_color=T.DANGER_HOVER,
            corner_radius=8,
            command=self._close_license_dialog_and_exit,
        ).grid(row=0, column=0, padx=(0, 10), sticky="w")
        ctk.CTkButton(
            actions,
            text="Activate Now",
            fg_color=T.ACCENT, hover_color=T.ACCENT_HOVER,
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

    def _submit_license_activation(self) -> None:
        passkey = self.license_entry.get().strip()
        if not passkey:
            self.license_message_var.set("Passkey is required.")
            return

        result = LicenseManager.activate_license(passkey)
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
        messagebox.showinfo("Activated", "Paid license activated successfully.")
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
        frame = self._new_view_frame("Campaigns")
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(2, weight=1)

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
                      text_color=T.ACCENT, font=ctk.CTkFont(size=11),
                      command=lambda: self._show_view("History"),
                      ).grid(row=0, column=1, sticky="e")

        list_card = ctk.CTkFrame(frame, fg_color=T.BG_SURFACE, corner_radius=14,
                                 border_width=1, border_color=T.BG_BORDER)
        list_card.grid(row=2, column=0, sticky="nsew")
        list_card.grid_rowconfigure(0, weight=1)
        list_card.grid_columnconfigure(0, weight=1)

        self.home_campaigns_scroll = ctk.CTkScrollableFrame(
            list_card, fg_color="transparent", corner_radius=0)
        self.home_campaigns_scroll.grid(row=0, column=0, sticky="nsew", padx=12, pady=12)
        self.home_campaigns_scroll.grid_columnconfigure(0, weight=1)
        self._bind_scrollable_frame_mousewheel(self.home_campaigns_scroll)

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
            ctk.CTkLabel(scroll, text="No campaigns yet. Start one with '+ New campaign' above.",
                         text_color=T.TEXT_MUTED, font=ctk.CTkFont(size=13),
                         ).grid(row=0, column=0, pady=32)
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
                         text_color=T.ACCENT, font=ctk.CTkFont(size=11, weight="bold"),
                         ).grid(row=0, column=index, padx=6)

        toolbar = ctk.CTkFrame(frame, fg_color=T.BG_SURFACE, corner_radius=14,
                               border_width=1, border_color=T.BG_BORDER)
        toolbar.grid_columnconfigure(3, weight=1)
        toolbar.grid(row=1, column=0, sticky="ew", pady=(0, 12))

        ctk.CTkButton(toolbar, text="Import Contacts",
                      corner_radius=8, fg_color=T.BADGE_BG, hover_color=T.BG_BORDER,
                      text_color=T.TEXT_HEAD, command=self._import_contacts).grid(
            row=0, column=0, padx=12, pady=12)
        ctk.CTkButton(toolbar, text="Export CSV", corner_radius=8,
                      fg_color=T.ACCENT, hover_color=T.ACCENT_HOVER,
                      text_color=T.TEXT_HEAD,
                      command=self._export_contacts_csv).grid(
            row=0, column=1, padx=(0, 12), pady=12)
        ctk.CTkButton(toolbar, text="Refresh", corner_radius=8,
                      fg_color=T.BG_SURFACE, hover_color=T.BG_SURFACE,
                      text_color=T.TEXT_MUTED,
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
            corner_radius=999, padx=12, pady=5, text_color=T.ACCENT, font=ctk.CTkFont(size=11))
        self.compose_contacts_chip.pack(side="left", padx=4)
        self.compose_delay_chip = ctk.CTkLabel(
            ch_meta, textvariable=self.compose_delay_var, fg_color=T.BADGE_BG,
            corner_radius=999, padx=12, pady=5, text_color=T.ACCENT, font=ctk.CTkFont(size=11))
        self.compose_delay_chip.pack(side="left", padx=4)
        self.compose_limit_chip = ctk.CTkLabel(
            ch_meta, textvariable=self.compose_limit_var, fg_color=T.BADGE_BG,
            corner_radius=999, padx=12, pady=5, text_color=T.ACCENT, font=ctk.CTkFont(size=11))
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
            fg_color=T.BG_SURFACE, button_color=T.BG_SURFACE,
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

        editor_frame = ctk.CTkFrame(self._wa_compose_frame, fg_color=T.BG_SURFACE, corner_radius=14,
                                    border_width=1, border_color=T.BG_BORDER)
        editor_frame.grid(row=1, column=0, sticky="nsew", padx=(0, 8))
        editor_frame.grid_columnconfigure(0, weight=1)
        editor_frame.grid_rowconfigure(2, weight=1)
        editor_frame.grid_rowconfigure(4, weight=1)

        ctk.CTkLabel(editor_frame, text="Message editor",
                     font=ctk.CTkFont(size=15, weight="bold"),
                     text_color=T.TEXT_HEAD).grid(
            row=0, column=0, padx=16, pady=(16, 8), sticky="w")

        variables_row = ctk.CTkFrame(editor_frame, fg_color="transparent")
        variables_row.grid(row=1, column=0, padx=14, pady=(0, 12), sticky="ew")
        for index, variable in enumerate(["{name}", "{amount}", "{date}", "{phone}"]):
            ctk.CTkButton(
                variables_row, text=variable, width=90,
                fg_color=T.BG_SURFACE, hover_color=T.BG_SURFACE, text_color=T.TEXT_MUTED,
                command=lambda token=variable: self._insert_variable(token),
            ).grid(row=0, column=index, padx=4, pady=4)

        self.message_textbox = ctk.CTkTextbox(editor_frame, fg_color=T.BG_INNER,
                                              text_color=T.TEXT_HEAD,
                                              border_width=1, border_color=T.BG_BORDER,
                                              wrap="word")
        self.message_textbox.grid(row=2, column=0, padx=16, pady=(0, 14), sticky="nsew")
        self.message_textbox.bind("<KeyRelease>", lambda _event: self._refresh_preview())

        ctk.CTkLabel(editor_frame, text="Contacts",
                     font=ctk.CTkFont(size=14, weight="bold"),
                     text_color=T.TEXT_HEAD).grid(
            row=3, column=0, padx=16, pady=(0, 6), sticky="w")
        self.compose_contacts_frame = ctk.CTkScrollableFrame(
            editor_frame, fg_color=T.BG_INNER, corner_radius=10,
            border_width=1, border_color=T.BG_BORDER)
        self.compose_contacts_frame.grid(row=4, column=0, padx=16, pady=(0, 16), sticky="nsew")
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
                     text_color=T.ACCENT, font=ctk.CTkFont(size=11)).grid(row=0, column=0, padx=4)
        ctk.CTkLabel(preview_chips, text="First 3 contacts", fg_color=T.BADGE_BG,
                     corner_radius=999, padx=10, pady=4,
                     text_color=T.ACCENT, font=ctk.CTkFont(size=11)).grid(row=0, column=1, padx=4)
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
        self._em_compose_frame.grid_rowconfigure(1, weight=1)

        # Email left column — compose area
        em_left = ctk.CTkFrame(self._em_compose_frame, fg_color=T.BG_SURFACE, corner_radius=14,
                               border_width=1, border_color=T.BG_BORDER)
        em_left.grid(row=0, column=0, rowspan=2, sticky="nsew", padx=(0, 8))
        em_left.grid_columnconfigure(0, weight=1)
        em_left.grid_rowconfigure(3, weight=1)

        ctk.CTkLabel(em_left, text="Email compose",
                     font=ctk.CTkFont(size=15, weight="bold"),
                     text_color=T.TEXT_HEAD).grid(row=0, column=0, padx=16, pady=(16, 8), sticky="w")

        em_fields = ctk.CTkFrame(em_left, fg_color="transparent")
        em_fields.grid(row=1, column=0, padx=16, pady=(0, 8), sticky="ew")
        em_fields.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(em_fields, text="Template", text_color=T.TEXT_MUTED,
                     font=ctk.CTkFont(size=11)).grid(row=0, column=0, padx=(0, 8), pady=(0, 6), sticky="w")

        def _on_em_tpl(val):
            subj, html = EMAIL_TEMPLATES.get(val, ("", ""))
            if subj:
                self._em_subj_var.set(subj)
            if html and hasattr(self, "_compose_em_body"):
                self._compose_em_body.delete("1.0", "end")
                self._compose_em_body.insert("1.0", html)

        ctk.CTkOptionMenu(em_fields, values=list(EMAIL_TEMPLATES.keys()),
                          variable=self._em_tpl_var, command=_on_em_tpl,
                          fg_color=T.BG_SURFACE, button_color=T.BG_SURFACE,
                          button_hover_color=T.BG_BORDER, text_color=T.TEXT_HEAD,
                          dropdown_fg_color=T.BG_SURFACE, dropdown_hover_color=T.BG_BORDER,
                          dropdown_text_color=T.TEXT_HEAD).grid(
            row=0, column=1, pady=(0, 6), sticky="ew")

        ctk.CTkLabel(em_fields, text="Subject", text_color=T.TEXT_MUTED,
                     font=ctk.CTkFont(size=11)).grid(row=1, column=0, padx=(0, 8), sticky="w")
        ctk.CTkEntry(em_fields, textvariable=self._em_subj_var,
                     fg_color=T.BG_INNER, border_color=T.BG_BORDER,
                     text_color=T.TEXT_HEAD).grid(row=1, column=1, sticky="ew")

        em_chips = ctk.CTkFrame(em_left, fg_color="transparent")
        em_chips.grid(row=2, column=0, padx=16, pady=(6, 8), sticky="w")
        ctk.CTkLabel(em_chips, text="Variables:", text_color=T.TEXT_MUTED,
                     font=ctk.CTkFont(size=11)).grid(row=0, column=0, padx=(0, 8))
        for i, v in enumerate(["{name}", "{email}", "{amount}", "{date}"]):
            ctk.CTkLabel(em_chips, text=v, fg_color=T.BG_SURFACE, corner_radius=999,
                         padx=10, pady=4, text_color=T.TEXT_MUTED,
                         font=ctk.CTkFont(size=11)).grid(row=0, column=i + 1, padx=4)

        self._compose_em_body = tk.Text(
            em_left, wrap="word", bg=T.resolve(T.BG_INNER), fg=T.resolve(T.TEXT_HEAD),
            insertbackground=T.resolve(T.TEXT_HEAD), font=("Courier New", 10),
            borderwidth=0, highlightthickness=0, relief="flat")
        self._compose_em_body.insert("1.0",
            "<p>Dear <strong>{name}</strong>,</p>\n<p>Your message here.</p>")
        self._compose_em_body.grid(row=3, column=0, padx=16, pady=(0, 16), sticky="nsew")

        # Email right column — SMTP status + recipients
        em_smtp_card = ctk.CTkFrame(self._em_compose_frame, fg_color=T.BG_SURFACE, corner_radius=14,
                                    border_width=1, border_color=T.BG_BORDER)
        em_smtp_card.grid(row=0, column=1, sticky="ew", pady=(0, 8))
        em_smtp_card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(em_smtp_card, text="SMTP connection",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=T.TEXT_HEAD).grid(row=0, column=0, padx=16, pady=(14, 4), sticky="w")
        self._em_smtp_status_var = StringVar(value="Not configured")
        self._em_smtp_chip = ctk.CTkLabel(
            em_smtp_card, textvariable=self._em_smtp_status_var,
            fg_color=T.BADGE_BG, corner_radius=999, padx=10, pady=4,
            text_color=T.DANGER, font=ctk.CTkFont(size=11))
        self._em_smtp_chip.grid(row=0, column=1, padx=16, pady=(14, 4), sticky="e")
        self._em_validation_label = ctk.CTkLabel(
            em_smtp_card, text="", text_color=T.DANGER,
            font=ctk.CTkFont(size=11), wraplength=240, justify="left")
        self._em_validation_label.grid(row=1, column=0, columnspan=2, padx=16, pady=(0, 4), sticky="w")
        ctk.CTkButton(em_smtp_card, text="Configure in Settings →", height=30, corner_radius=6,
                      fg_color=T.BADGE_BG, hover_color=T.BG_BORDER, text_color=T.ACCENT,
                      font=ctk.CTkFont(size=11),
                      command=lambda: self._show_view("Settings")).grid(
            row=2, column=0, columnspan=2, padx=16, pady=(0, 14), sticky="w")

        em_recip_card = ctk.CTkFrame(self._em_compose_frame, fg_color=T.BG_SURFACE, corner_radius=14,
                                     border_width=1, border_color=T.BG_BORDER)
        em_recip_card.grid(row=1, column=1, sticky="nsew")
        em_recip_card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(em_recip_card, text="Recipients",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=T.TEXT_HEAD).grid(row=0, column=0, padx=16, pady=(14, 4), sticky="w")
        ctk.CTkLabel(em_recip_card, textvariable=self._em_compose_count_var,
                     text_color=T.ACCENT, font=ctk.CTkFont(size=13, weight="bold")).grid(
            row=1, column=0, padx=16, pady=(0, 4), sticky="w")
        ctk.CTkLabel(em_recip_card,
                     text="Sends to all contacts with an email address.\nManage contacts in the Contacts tab.",
                     text_color=T.TEXT_MUTED, font=ctk.CTkFont(size=11), justify="left").grid(
            row=2, column=0, padx=16, pady=(0, 14), sticky="w")

        def _smtp_changed(*_):
            if not hasattr(self, "_em_smtp_chip"):
                return
            if self._em_user.get():
                self._em_smtp_status_var.set(f"{self._em_provider.get()} · {self._em_user.get()}")
                self._em_smtp_chip.configure(text_color=T.SUCCESS)
            else:
                self._em_smtp_status_var.set("Not configured")
                self._em_smtp_chip.configure(text_color=T.DANGER)

        self._em_user.trace_add("write", _smtp_changed)
        self._em_provider.trace_add("write", _smtp_changed)

        # ── Row 2: Shared send controls ────────────────────────────────────────
        controls = ctk.CTkFrame(frame, fg_color=T.BG_SURFACE, corner_radius=14,
                                border_width=1, border_color=T.BG_BORDER)
        controls.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        controls.grid_columnconfigure(3, weight=1)

        ctk.CTkButton(controls, text="Start", width=90,
                      fg_color=T.ACCENT, hover_color=T.ACCENT_HOVER,
                      text_color=T.TEXT_HEAD,
                      corner_radius=8, font=ctk.CTkFont(size=13, weight="bold"),
                      command=self._dispatch_send).grid(
            row=0, column=0, padx=(16, 8), pady=(14, 8))
        self._compose_pause_btn = ctk.CTkButton(
            controls, text="Pause / Resume", width=120,
            fg_color="transparent", hover_color=T.BG_SURFACE,
            border_width=1, border_color=T.ACCENT,
            text_color=T.ACCENT, corner_radius=8,
            command=self._toggle_pause)
        self._compose_pause_btn.grid(row=0, column=1, padx=8, pady=(14, 8))
        ctk.CTkButton(controls, text="Stop", width=80,
                      fg_color=T.DANGER, hover_color=T.DANGER_HOVER,
                      text_color=T.TEXT_HEAD,
                      corner_radius=8, command=self._dispatch_stop).grid(
            row=0, column=2, padx=8, pady=(14, 8))

        prog_row = ctk.CTkFrame(controls, fg_color="transparent")
        prog_row.grid(row=1, column=0, columnspan=4, padx=16, pady=(0, 12), sticky="ew")
        prog_row.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(prog_row, textvariable=self.progress_status_var,
                     text_color=T.TEXT_MUTED, font=ctk.CTkFont(size=11), anchor="w").grid(
            row=0, column=0, sticky="w")
        self.compose_progress = ctk.CTkProgressBar(prog_row, height=8, corner_radius=4,
                                                    progress_color=T.ACCENT, fg_color=T.BG_SURFACE)
        self.compose_progress.grid(row=1, column=0, sticky="ew", pady=(4, 0))
        self.compose_progress.set(0)

    def _on_channel_switch(self, channel: str) -> None:
        if channel == "WhatsApp":
            self._wa_compose_frame.grid()
            self._em_compose_frame.grid_remove()
            self._compose_pause_btn.configure(state="normal")
        else:
            self._wa_compose_frame.grid_remove()
            self._em_compose_frame.grid()
            self._compose_pause_btn.configure(state="disabled")
            self._refresh_compose_email_recipients()

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

    def _refresh_compose_email_recipients(self) -> None:
        if not hasattr(self, "_em_compose_count_var"):
            return
        count = sum(1 for c in self.contacts if c.email)
        self._em_compose_count_var.set(
            f"{count} contact{'s' if count != 1 else ''} with email")

    def _start_email_from_compose(self) -> None:
        if self._em_send_thread and self._em_send_thread.is_alive():
            messagebox.showinfo("Campaign Running", "An email campaign is already in progress.")
            return

        contacts = [c for c in self.contacts if c.email]
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
        if hasattr(self, "_em_validation_label"):
            self._em_validation_label.configure(text="")
        html_template = self._compose_em_body.get("1.0", "end") if hasattr(
            self, "_compose_em_body") else ""
        if not html_template.strip():
            self.progress_status_var.set("⚠ Email body is empty.")
            return
        if not messagebox.askyesno("Confirm send",
                f"Send email to {len(contacts)} contacts?\n\n"
                "Make sure you have their consent (legal requirement)."):
            return

        self._em_stop_flag.clear()
        self.compose_progress.set(0)
        self.progress_status_var.set("Connecting to SMTP…")

        subject_template = self._em_subj_var.get()

        def sub(text, m):
            for k, v in m.items():
                text = text.replace(f"{{{k}}}", str(v))
            return text

        recipients = []
        for contact in contacts:
            vars_map = {
                "name": contact.name, "email": contact.email,
                "phone": contact.phone, "sender": self._em_from_name.get(),
            }
            vars_map.update(contact.custom_fields)
            recipients.append(
                (contact, sub(subject_template, vars_map), sub(html_template, vars_map)))

        campaign_name = f"Email {datetime.now().strftime('%Y-%m-%d %H:%M')}"

        def worker():
            def progress(sent, total, to_addr):
                def _upd():
                    self.progress_status_var.set(f"Sent: {sent} / {total} — {to_addr}")
                    self.compose_progress.set(sent / total)
                self.after(0, _upd)

            try:
                result = self._send_email_campaign(
                    recipients, campaign_name,
                    progress_callback=progress, stop_flag=self._em_stop_flag)
            except Exception as ex:
                self.after(0, lambda: self.progress_status_var.set(f"⚠ SMTP error: {ex}"))
                return

            def finish():
                self.compose_progress.set(1)
                self.progress_status_var.set(
                    f"Done — ✅ {result['sent']} sent  ❌ {result['failed']} failed")
                messagebox.showinfo("Email campaign complete",
                                    f"Sent: {result['sent']}\nFailed: {result['failed']}")

            self.after(0, finish)

        self._em_send_thread = threading.Thread(target=worker, daemon=True)
        self._em_send_thread.start()

    def _send_email_campaign(self, recipients, campaign_name: str,
                              progress_callback=None, stop_flag=None) -> dict:
        """Send pre-resolved (contact, subject, html_body) tuples over SMTP,
        logging each to message_logs. Shared by Compose and AI Cards sends.

        Returns {"sent": int, "failed": int, "campaign_id": Optional[int]}.
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

        for contact, subject, html_body in recipients:
            if stop_flag is not None and stop_flag.is_set():
                break
            to_addr = (contact.email or "").strip()
            try:
                msg = MIMEMultipart("alternative")
                msg["Subject"] = subject
                msg["From"] = f"{self._em_from_name.get()} <{self._em_from_addr.get()}>"
                msg["To"] = to_addr
                msg.attach(MIMEText(html_body, "html", "utf-8"))
                conn.sendmail(self._em_from_addr.get(), to_addr, msg.as_string())
                sent += 1
                db.add_message_log(MessageLog(
                    campaign_id=campaign_id, contact_email=to_addr,
                    contact_name=contact.name, subject=subject,
                    message_text=html_body, status=MessageStatus.SENT,
                    sent_at=datetime.now(),
                ))
                if progress_callback:
                    progress_callback(sent, total, to_addr)
            except Exception as ex:
                db.add_message_log(MessageLog(
                    campaign_id=campaign_id, contact_email=to_addr,
                    contact_name=contact.name, subject=subject,
                    message_text=html_body, status=MessageStatus.FAILED,
                    error_message=str(ex),
                ))

            time.sleep(float(self._em_delay.get() or 5))

        try:
            conn.quit()
        except Exception:
            pass

        if campaign_id:
            db.update_campaign(campaign_id, sent, total - sent)

        return {"sent": sent, "failed": total - sent, "campaign_id": campaign_id}

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
                self.after(0, lambda: callback(False, str(ex)))

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
                     text_color=T.ACCENT, font=ctk.CTkFont(size=11, weight="bold"),
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
        ctk.CTkLabel(rate_frame, text="Delivery Rate",
                     font=ctk.CTkFont(size=14, weight="bold"),
                     text_color=T.TEXT_HEAD).grid(
            row=0, column=0, padx=16, pady=14, sticky="w")
        ctk.CTkLabel(rate_frame, text="Analytics Stream", fg_color=T.BADGE_BG,
                     corner_radius=999, padx=10, pady=5,
                     text_color=T.ACCENT, font=ctk.CTkFont(size=11),
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
        ctk.CTkOptionMenu(
            actions,
            values=["today", "week", "month", "all"],
            variable=self.report_period_var,
            command=lambda _value: self._refresh_stats(
                update_chart=True, update_text_feeds=True, update_dashboard_periods=True),
            fg_color=T.BG_SURFACE, button_color=T.BG_SURFACE,
            button_hover_color=T.BG_BORDER, text_color=T.TEXT_HEAD,
            dropdown_fg_color=T.BG_SURFACE, dropdown_hover_color=T.BG_BORDER,
            dropdown_text_color=T.TEXT_HEAD,
        ).grid(row=0, column=1, padx=(0, 12), pady=8)
        ctk.CTkLabel(actions, text="Export Format", text_color=T.TEXT_HEAD).grid(
            row=0, column=2, padx=(0, 8), pady=8)
        ctk.CTkOptionMenu(
            actions,
            values=["csv", "pdf"],
            variable=self.report_format_var,
            command=lambda _value: self._update_report_summary(),
            fg_color=T.BG_SURFACE, button_color=T.BG_SURFACE,
            button_hover_color=T.BG_BORDER, text_color=T.TEXT_HEAD,
            dropdown_fg_color=T.BG_SURFACE, dropdown_hover_color=T.BG_BORDER,
            dropdown_text_color=T.TEXT_HEAD,
        ).grid(row=0, column=3, padx=(0, 12), pady=8)
        ctk.CTkButton(actions, text="Export Report", corner_radius=8,
                      fg_color=T.ACCENT, hover_color=T.ACCENT_HOVER,
                      text_color=T.TEXT_HEAD,
                      command=self._export_report).grid(row=0, column=4, pady=8)
        ctk.CTkLabel(actions, textvariable=self.report_export_status_var,
                     fg_color=T.BADGE_BG, corner_radius=999, padx=12, pady=5,
                     text_color=T.ACCENT, font=ctk.CTkFont(size=11),
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
        hero.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        hero.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(hero, text="Campaign history",
                     font=ctk.CTkFont(size=15, weight="bold"),
                     text_color=T.TEXT_HEAD).grid(
            row=0, column=0, padx=18, pady=(14, 4), sticky="w")
        ctk.CTkLabel(hero, text="Full log of all email campaigns. Use Duplicate to re-use a campaign.",
                     text_color=T.TEXT_MUTED, font=ctk.CTkFont(size=12),
                     ).grid(row=1, column=0, padx=18, pady=(0, 14), sticky="w")
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
            empty_text = ("No campaigns match that search."
                          if q else
                          "No campaigns yet. Start an email campaign to see history here.")
            ctk.CTkLabel(self._history_scroll, text=empty_text,
                         text_color=T.TEXT_MUTED, font=ctk.CTkFont(size=13),
                         ).grid(row=0, column=0, pady=40)
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
            status = "sent" if sent > 0 else "failed" if failed > 0 else "draft"

            ctk.CTkLabel(row_frame, text=name,
                         font=ctk.CTkFont(size=13, weight="bold"),
                         text_color=T.TEXT_HEAD).grid(
                row=0, column=0, padx=14, pady=(10, 2), sticky="w")
            ctk.CTkLabel(row_frame,
                         text=f"📅 {created}  ·  ✅ {sent} sent  ·  ❌ {failed} failed",
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

            ctk.CTkButton(actions, text="Duplicate", width=80, corner_radius=6,
                          fg_color=T.BADGE_BG, hover_color=T.BG_BORDER,
                          text_color=T.TEXT_HEAD, command=duplicate).pack(side="left", padx=4)

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
            messagebox.showinfo("Exported", f"Saved {len(campaigns)} campaigns to:\n{path}")
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
                         text_color=T.ACCENT, font=ctk.CTkFont(size=11),
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

        ctk.CTkLabel(card, text="Delay between messages",
                     text_color=T.TEXT_HEAD).grid(row=2, column=0, padx=16, pady=10, sticky="w")
        self.delay_slider = ctk.CTkSlider(card, from_=10, to=120, number_of_steps=110, command=self._on_delay_change)
        self.delay_slider.grid(row=2, column=1, padx=16, pady=10, sticky="ew")
        self.delay_slider.set(self.delay_var.get())
        self.delay_label = ctk.CTkLabel(card, text=f"{self.delay_var.get()} sec",
                                        text_color=T.TEXT_MUTED)
        self.delay_label.grid(row=2, column=2, padx=(0, 16), pady=10, sticky="e")

        ctk.CTkLabel(card, text="Daily limit",
                     text_color=T.TEXT_HEAD).grid(row=3, column=0, padx=16, pady=10, sticky="w")
        self.limit_slider = ctk.CTkSlider(card, from_=10, to=500, number_of_steps=98, command=self._on_daily_limit_change)
        self.limit_slider.grid(row=3, column=1, padx=16, pady=10, sticky="ew")
        self.limit_slider.set(self.daily_limit_var.get())
        self.limit_label = ctk.CTkLabel(card, text=str(self.daily_limit_var.get()),
                                        text_color=T.TEXT_MUTED)
        self.limit_label.grid(row=3, column=2, padx=(0, 16), pady=10, sticky="e")

        self.limit_warning_label = ctk.CTkLabel(card, text="", text_color=T.DANGER)
        self.limit_warning_label.grid(row=4, column=1, padx=16, pady=(0, 12), sticky="w")

        ctk.CTkSwitch(card, text="Random jitter", variable=self.jitter_var,
                      text_color=T.TEXT_HEAD, command=self._save_settings).grid(
            row=5, column=0, padx=16, pady=10, sticky="w"
        )
        ctk.CTkSwitch(card, text="Consent required", variable=self.consent_required_var,
                      text_color=T.TEXT_HEAD, command=self._save_settings).grid(
            row=5, column=1, padx=16, pady=10, sticky="w"
        )

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
        ctk.CTkLabel(system_card, text="Theme selector",
                     text_color=T.TEXT_HEAD).grid(row=2, column=0, padx=16, pady=(0, 6), sticky="w")
        ctk.CTkOptionMenu(
            system_card,
            values=["Dark", "Light", "Warm Ivory", "System"],
            variable=self.theme_var,
            command=self._on_theme_selected,
            fg_color=T.BG_SURFACE, button_color=T.BG_SURFACE,
            button_hover_color=T.BG_BORDER, text_color=T.TEXT_HEAD,
            dropdown_fg_color=T.BG_SURFACE, dropdown_hover_color=T.BG_BORDER,
            dropdown_text_color=T.TEXT_HEAD,
        ).grid(row=3, column=0, padx=16, pady=(0, 12), sticky="w")

        session_strip = ctk.CTkFrame(system_card, fg_color=T.BG_INNER, corner_radius=12,
                                     border_width=1, border_color=T.BG_BORDER)
        session_strip.grid(row=4, column=0, padx=16, pady=(0, 12), sticky="ew")
        ctk.CTkLabel(session_strip, text="Session Status",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=T.TEXT_HEAD).pack(anchor="w", padx=14, pady=(12, 4))
        ctk.CTkLabel(session_strip, textvariable=self.session_status_var,
                     text_color=T.TEXT_MUTED, wraplength=360, justify="left").pack(
            anchor="w", padx=14, pady=(0, 12))
        ctk.CTkButton(system_card, text="Reset Session", corner_radius=8,
                      fg_color=T.DANGER, hover_color=T.DANGER_HOVER,
                      text_color=T.TEXT_HEAD,
                      command=self._reset_session).grid(
            row=5, column=0, padx=16, pady=(0, 8), sticky="w")
        ctk.CTkButton(system_card, text="Re-run Setup Wizard", corner_radius=8,
                      fg_color=T.ACCENT, hover_color=T.ACCENT_HOVER,
                      text_color=T.TEXT_HEAD,
                      command=self._reopen_setup_wizard).grid(
            row=6, column=0, padx=16, pady=(0, 16), sticky="w")

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
                         text_color=T.ACCENT).pack(anchor="w", padx=12, pady=(0, 12))

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
            text_color=T.ACCENT,
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

        ctk.CTkLabel(smtp_card, text="Provider", text_color=T.TEXT_HEAD).grid(
            row=2, column=0, padx=16, pady=6, sticky="w")
        ctk.CTkOptionMenu(smtp_card, values=list(SMTP_PRESETS.keys()),
                          variable=self._em_provider, command=_on_preset,
                          fg_color=T.BG_SURFACE, button_color=T.BG_SURFACE,
                          button_hover_color=T.BG_BORDER, text_color=T.TEXT_HEAD,
                          dropdown_fg_color=T.BG_SURFACE, dropdown_hover_color=T.BG_BORDER,
                          dropdown_text_color=T.TEXT_HEAD).grid(
            row=2, column=1, padx=(4, 16), pady=6, sticky="ew")

        for i, (lbl, var, secret) in enumerate([
            ("Host",         self._em_host,      False),
            ("Port",         self._em_port,      False),
            ("Username",     self._em_user,      False),
            ("Password",     self._em_pass,      True),
            ("Sender name",  self._em_from_name, False),
            ("Sender email", self._em_from_addr, False),
            ("Delay (sec)",  self._em_delay,     False),
        ], start=3):
            ctk.CTkLabel(smtp_card, text=lbl, text_color=T.TEXT_HEAD).grid(
                row=i, column=0, padx=16, pady=5, sticky="w")
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

        ctk.CTkLabel(ai_card, text="API key", text_color=T.TEXT_HEAD).grid(
            row=2, column=0, padx=16, pady=6, sticky="w")
        self._ai_key_entry = ctk.CTkEntry(
            ai_card, textvariable=self._ai_api_key, show="●",
            fg_color=T.BG_INNER, border_color=T.BG_BORDER, text_color=T.TEXT_HEAD)
        self._ai_key_entry.grid(row=2, column=1, padx=(4, 8), pady=6, sticky="ew")

        def _toggle_ai_key_visible():
            visible = not self._ai_key_visible.get()
            self._ai_key_visible.set(visible)
            self._ai_key_entry.configure(show="" if visible else "●")
            self._ai_key_toggle_btn.configure(text="Hide" if visible else "Show")

        self._ai_key_toggle_btn = ctk.CTkButton(
            ai_card, text="Show", width=70, corner_radius=8,
            fg_color=T.BG_INNER, hover_color=T.BG_BORDER, text_color=T.TEXT_HEAD,
            command=_toggle_ai_key_visible)
        self._ai_key_toggle_btn.grid(row=2, column=2, padx=(0, 16), pady=6, sticky="e")

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
        ai_actions.grid(row=3, column=0, columnspan=3, padx=16, pady=(0, 16), sticky="ew")
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

            def worker():
                try:
                    ai_service.validate_api_key(api_key)
                    self.after(0, lambda: messagebox.showinfo("AI key test", "Key is valid ✅"))
                except AIServiceError as ex:
                    self.after(0, lambda: messagebox.showerror("AI key test failed", str(ex)))
            threading.Thread(target=worker, daemon=True).start()

        ctk.CTkButton(ai_actions, text="Test key", corner_radius=8,
                      fg_color=T.BG_INNER, hover_color=T.BG_BORDER, text_color=T.TEXT_HEAD,
                      command=_test_ai_key).pack(side="left", padx=(0, 10))
        ctk.CTkLabel(ai_actions, textvariable=self._ai_key_status_var,
                     text_color=T.TEXT_MUTED, font=ctk.CTkFont(size=12)).pack(side="left")

        self._update_settings_summary()
        self._update_daily_limit_warning()

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

    def _show_view(self, view_name: str) -> None:
        self._active_view = view_name
        self._apply_view_chrome(view_name)
        self.header_title.configure(text=view_name)
        for name, frame in self.view_containers.items():
            if name == view_name:
                frame.grid()
            else:
                frame.grid_remove()
        for name, button in self.sidebar_buttons.items():
            is_active = name == view_name
            button.configure(
                fg_color=T.ACCENT if is_active else T.NAV_INACTIVE,
                hover_color=T.ACCENT_HOVER if is_active else T.BG_SURFACE,
                border_width=0,
                text_color=T.TEXT_HEAD,
                font=ctk.CTkFont(size=13, weight="bold" if is_active else "normal"),
            )
            if name in self.sidebar_accent_bars:
                self.sidebar_accent_bars[name].configure(
                    bg=T.resolve(T.ACCENT if is_active else T.BG_MAIN)
                )
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
            {"theme": "Dark", "delay": 30, "daily_limit": 50, "jitter": True, "consent_required": True},
        )
        self.theme_var.set(str(settings.get("theme", "Dark")))
        self.delay_var.set(int(settings.get("delay", 30)))
        self.daily_limit_var.set(int(settings.get("daily_limit", 50)))
        self.jitter_var.set(bool(settings.get("jitter", True)))
        self.consent_required_var.set(bool(settings.get("consent_required", True)))

        # SMTP — stored in same JSON blob (plaintext in local SQLite, AppData only)
        self._em_provider.set(str(settings.get("smtp_provider", "Gmail")))
        self._em_host.set(str(settings.get("smtp_host", "smtp.gmail.com")))
        self._em_port.set(str(settings.get("smtp_port", "587")))
        self._em_user.set(str(settings.get("smtp_user", "")))
        self._em_pass.set(str(settings.get("smtp_pass", "")))
        self._em_from_name.set(str(settings.get("smtp_from_name", "My Business")))
        self._em_from_addr.set(str(settings.get("smtp_from_addr", "")))
        self._em_delay.set(str(settings.get("smtp_delay", "5")))

        # AI Cards API key — encrypted at rest, decrypted only into memory here
        ai_key = decrypt_secret(str(settings.get("ai_api_key_enc", "")))
        self._ai_api_key.set(ai_key)
        self._ai_key_status_var.set("API key saved (encrypted)" if ai_key else "No API key saved")

        # First-run setup wizard progress (plain attrs, not Tk Variables —
        # nothing binds to these continuously, only read/written at step transitions)
        self.setup_wizard_completed = bool(settings.get("setup_wizard_completed", False))
        self.setup_wizard_skipped = bool(settings.get("setup_wizard_skipped", False))
        self.setup_wizard_channels = list(settings.get("setup_wizard_channels", []))
        self.setup_wizard_channel_index = int(settings.get("setup_wizard_channel_index", 0))
        self.setup_wizard_substep = str(settings.get("setup_wizard_substep", ""))

    def _save_settings(self) -> None:
        self.db.set_setting_json(
            self.SETTINGS_KEY,
            {
                "theme": self.theme_var.get(),
                "delay": self.delay_var.get(),
                "daily_limit": self.daily_limit_var.get(),
                "jitter": self.jitter_var.get(),
                "consent_required": self.consent_required_var.get(),
                # SMTP
                "smtp_provider":   self._em_provider.get(),
                "smtp_host":       self._em_host.get(),
                "smtp_port":       self._em_port.get(),
                "smtp_user":       self._em_user.get(),
                "smtp_pass":       self._em_pass.get(),
                "smtp_from_name":  self._em_from_name.get(),
                "smtp_from_addr":  self._em_from_addr.get(),
                "smtp_delay":      self._em_delay.get(),
                # AI Cards
                "ai_api_key_enc":  encrypt_secret(self._ai_api_key.get()),
                # Setup wizard progress
                "setup_wizard_completed":     self.setup_wizard_completed,
                "setup_wizard_skipped":       self.setup_wizard_skipped,
                "setup_wizard_channels":      self.setup_wizard_channels,
                "setup_wizard_channel_index": self.setup_wizard_channel_index,
                "setup_wizard_substep":       self.setup_wizard_substep,
            },
        )
        self._update_settings_summary()
        self._refresh_stats(update_text_feeds=True, update_dashboard_periods=True)

    def _apply_theme(self, selected_theme: str) -> None:
        prev_palette = T.get_palette()
        if selected_theme == "Warm Ivory":
            T.set_palette("warm_ivory")
            ctk.set_appearance_mode("Light")
        else:
            ctk.set_appearance_mode(selected_theme)  # "Dark" / "Light" / "System"
            T.set_palette("light" if ctk.get_appearance_mode() == "Light" else "dark")
        new_palette = T.get_palette()

        if not hasattr(self, "view_host"):
            return  # still inside __init__, before _create_ui() — nothing to refresh yet

        # Warm Ivory is a genuine 3rd palette CTk's binary appearance mode can't
        # represent — already-built widgets can't pick it up in place, so a full
        # rebuild is required entering or leaving it (see theme.py docstring).
        entering_or_leaving_warm = (prev_palette == "warm_ivory") != (new_palette == "warm_ivory")
        if entering_or_leaving_warm:
            self.after_idle(self._rebuild_ui_for_theme)
        else:
            self.after_idle(self._sync_theme_overrides)

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
        return "Trial expired. Activate with your paid passkey to continue using MessageCannon."

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
        self.compose_contacts_var.set(f"{selected_count} selected")
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
        self._update_compose_summary()
        self._save_settings()

    def _on_daily_limit_change(self, value: float) -> None:
        rounded = int(round(value))
        self.daily_limit_var.set(rounded)
        self.limit_label.configure(text=str(rounded))
        self._update_daily_limit_warning()
        self._update_compose_summary()
        self._save_settings()

    def _update_daily_limit_warning(self) -> None:
        if self.daily_limit_var.get() > 50:
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
                text_color=T.ACCENT, font=ctk.CTkFont(size=11),
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
            ctk.CTkLabel(top, text="Active",
                         fg_color=T.BADGE_BG, corner_radius=999,
                         padx=8, pady=3,
                         text_color=T.ACCENT, font=ctk.CTkFont(size=10, weight="bold"),
                         ).pack(anchor="e", side="right")
            ctk.CTkLabel(card, text=contact.phone, text_color=T.TEXT_MUTED,
                         font=ctk.CTkFont(size=12)).pack(anchor="w", padx=16, pady=(0, 3))
            footer = ctk.CTkFrame(card, fg_color="transparent")
            footer.pack(fill="x", padx=16, pady=(0, 12))
            ctk.CTkLabel(footer,
                         text=f"ID {contact.id if contact.id is not None else '—'}",
                         text_color=T.TEXT_MUTED, font=ctk.CTkFont(size=11),
                         ).pack(side="left")
            ctk.CTkLabel(footer, text="Ready for campaign",
                         text_color=T.SUCCESS, font=ctk.CTkFont(size=10, weight="bold"),
                         ).pack(side="right")

        self._bind_scrollable_frame_mousewheel(self.contacts_directory)

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
        for variable in self.contact_selection_vars.values():
            variable.set(selected)
        self._update_compose_summary()
        self._refresh_preview()

    def _insert_variable(self, token: str) -> None:
        self.message_textbox.insert("insert", token)
        self._refresh_preview()

    def _on_template_selected(self, template_name: str) -> None:
        if template_name == "Custom Message":
            return
        template = next((item for item in self.templates if item.name == template_name), None)
        if template is None:
            return
        self.message_textbox.delete("1.0", "end")
        self.message_textbox.insert("1.0", template.message_text)
        self._refresh_preview()

    def _refresh_preview(self) -> None:
        template = self.message_textbox.get("1.0", "end").strip() if hasattr(self, "message_textbox") else ""
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
            key = self._contact_key(contact, index)
            variable = self.contact_selection_vars.get(key)
            if variable and variable.get():
                selected.append(contact)
        return selected

    def _import_contacts(self) -> None:
        file_path = filedialog.askopenfilename(
            title="Import Contacts",
            filetypes=[
                ("All supported", "*.csv *.xls *.xlsx *.xlsm *.html *.htm *.json *.vcf"),
                ("CSV", "*.csv"),
                ("Excel", "*.xls *.xlsx *.xlsm"),
                ("HTML", "*.html *.htm"),
                ("JSON", "*.json"),
                ("vCard", "*.vcf"),
            ],
        )
        if not file_path:
            return

        self.progress_status_var.set("Importing contacts...")
        self._log_activity(f"Import started from {Path(file_path).name}")

        def worker() -> None:
            try:
                imported_count, errors = self.contact_manager.import_from_file(file_path)
                self.after(0, lambda: self._finish_import(imported_count, errors, file_path))
            except Exception as exc:
                Logger.error(f"Contact import failed: {exc}")
                self.after(0, lambda: messagebox.showerror("Import Failed", str(exc)))
                self.after(0, lambda: self.progress_status_var.set("Import failed"))

        threading.Thread(target=worker, daemon=True).start()

    def _finish_import(self, imported_count: int, errors: List[str], file_path: str) -> None:
        self._reload_contacts()
        self.progress_status_var.set("Ready")
        if errors:
            messagebox.showwarning(
                "Import completed with warnings",
                f"Imported {imported_count} contacts\n\n" + "\n".join(errors[:10]),
            )
        else:
            messagebox.showinfo("Contacts Imported", f"Imported {imported_count} contacts successfully.")
        self._log_activity(f"Imported {imported_count} contacts from {Path(file_path).name}")

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
            messagebox.showinfo("Export Complete", f"Exported {len(contacts)} contacts to:\n{path}")
            self._log_activity(f"Exported {len(contacts)} contacts to CSV")
        except Exception as exc:
            Logger.error(f"Export failed: {exc}")
            messagebox.showerror("Export Failed", str(exc))

    def _start_session_bootstrap(self) -> None:
        if self.license_locked:
            return

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
                     text_color=T.ACCENT, font=ctk.CTkFont(size=12, weight="bold")).grid(
            row=0, column=0, padx=14, pady=10, sticky="w")
        ctk.CTkButton(banner, text="Resume setup", width=110, height=28, corner_radius=6,
                      fg_color=T.ACCENT, hover_color=T.ACCENT_HOVER, text_color=T.TEXT_HEAD,
                      font=ctk.CTkFont(size=11), command=self._resume_setup_wizard).grid(
            row=0, column=1, padx=(0, 14), pady=10, sticky="e")

    def _reset_session(self) -> None:
        if not messagebox.askyesno("Reset Session", "Clear the saved WhatsApp session and require a fresh QR scan?"):
            return
        self.whatsapp_sender.reset_session()
        self._set_session_status("Session expired - please scan QR")
        self._log_activity("Saved WhatsApp session cleared")

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

        template = self.message_textbox.get("1.0", "end").strip()
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

        self.compose_progress.set(0)
        self.progress_status_var.set("Preparing campaign...")
        self._log_activity(f"Campaign queued for {len(selected_contacts)} contacts")

        def worker() -> None:
            try:
                result = self.whatsapp_sender.send_messages(
                    contacts=selected_contacts,
                    messages=messages,
                    delay=self.delay_var.get(),
                    use_jitter=self.jitter_var.get(),
                    max_messages=self.daily_limit_var.get(),
                    progress_callback=self._handle_send_progress,
                    event_callback=self._handle_sender_event,
                )
                self.after(0, lambda: self.progress_status_var.set(
                    f"Completed: {result.get('sent', 0)} sent, {result.get('failed', 0)} failed"
                ))
                self._log_activity(
                    f"Campaign completed with {result.get('sent', 0)} sent and {result.get('failed', 0)} failed"
                )
            except Exception as exc:
                Logger.error(f"Campaign send failed: {exc}")
                self.after(0, lambda: self.progress_status_var.set("Campaign failed"))
                self._log_activity(f"Campaign failed: {exc}")
            finally:
                self.after(0, lambda: self._refresh_stats(update_dashboard_periods=True))

        self.send_thread = threading.Thread(target=worker, daemon=True)
        self.send_thread.start()

    def _toggle_pause(self) -> None:
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
        self.compose_progress.set(current / total if total else 0)
        self.progress_status_var.set(f"{status_text} ({current}/{total})")

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

            self.dashboard_cards["Sent Today"].configure(text=str(today_stats.get("sent_count", 0)))
            self.dashboard_cards["Delivery Rate"].configure(text=str(delivered_count))
            self.dashboard_cards["Active Session"].configure(text="Active" if session_state.is_active else "Scan QR")
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
