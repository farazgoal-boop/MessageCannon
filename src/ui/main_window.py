"""Modern CustomTkinter main window for MessageCannon."""

from __future__ import annotations

import json
import os
import sys
import threading
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
from ..models import Contact, Template
from ..utils.constants import APP_NAME, APP_VERSION, WINDOW_HEIGHT, WINDOW_WIDTH
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
        self.view_frames: Dict[str, ctk.CTkFrame] = {}
        self.view_containers: Dict[str, object] = {}
        self.activity_items: List[str] = []
        self.send_thread: Optional[threading.Thread] = None
        self.license_dialog: Optional[ctk.CTkToplevel] = None
        self.license_locked = False
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
        self.report_export_status_var = StringVar(value="CSV export ready")

        self.title(f"{APP_NAME} v{APP_VERSION}")
        self.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.minsize(1220, 760)
        self.configure(fg_color="#0a1118")
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
        self._refresh_stats()
        self._refresh_preview()
        self._show_view("Dashboard")

        self.after(800, self._start_session_bootstrap)
        self.after(5000, self._periodic_refresh)

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

    def _sync_widget_theme(self, widget: object) -> None:
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
            for child in widget.winfo_children():
                self._sync_widget_theme(child)

    def _sync_theme_overrides(self) -> None:
        self._sync_widget_theme(self)
        if self.license_dialog is not None and self.license_dialog.winfo_exists():
            self._sync_widget_theme(self.license_dialog)

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
        self.sidebar = ctk.CTkFrame(self, width=240, corner_radius=0, fg_color="#0c1620")
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(7, weight=1)

        brand_panel = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        brand_panel.grid(row=0, column=0, padx=20, pady=(24, 18), sticky="ew")
        brand_panel.grid_columnconfigure(1, weight=1)

        if self.brand_logo is not None:
            ctk.CTkLabel(brand_panel, text="", image=self.brand_logo).grid(row=0, column=0, rowspan=2, padx=(4, 14), sticky="w")

        brand = ctk.CTkLabel(
            brand_panel,
            text="MessageCannon\nControl Center",
            justify="left",
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color="#dbe8f0",
        )
        brand.grid(row=0, column=1, sticky="w")

        ctk.CTkLabel(
            brand_panel,
            text="Premium Campaign Workspace",
            text_color="#6d8798",
            font=ctk.CTkFont(size=12, weight="bold"),
        ).grid(row=1, column=1, pady=(2, 0), sticky="w")

        nav_items = [
            ("Dashboard", "DB   Dashboard"),
            ("Contacts", "CT   Contacts"),
            ("Compose", "CP   Compose"),
            ("Reports", "RP   Reports"),
            ("Email",    "EM   Email"),
            ("Cards",     "CC   Card Creator"),
            ("Settings", "ST   Settings"),
        ]
        for row_index, (view_name, label) in enumerate(nav_items, start=1):
            button = ctk.CTkButton(
                self.sidebar,
                text=label,
                anchor="w",
                height=46,
                corner_radius=16,
                fg_color="transparent",
                hover_color="#203243",
                border_width=1,
                border_color="#183144",
                text_color="#dbe8f0",
                command=lambda name=view_name: self._show_view(name),
            )
            button.grid(row=row_index, column=0, padx=18, pady=6, sticky="ew")
            self.sidebar_buttons[view_name] = button

        self.sidebar_premium_panel = ctk.CTkFrame(self.sidebar, fg_color="#101f2b", corner_radius=18)
        self.sidebar_premium_panel.grid(row=8, column=0, padx=18, pady=(18, 8), sticky="ew")
        self.sidebar_premium_panel.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            self.sidebar_premium_panel,
            text="Premium Access",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).grid(row=0, column=0, padx=14, pady=(14, 4), sticky="w")
        ctk.CTkLabel(
            self.sidebar_premium_panel,
            text="Persistent sessions, live delivery analytics, and campaign-grade controls.",
            text_color="#88a0af",
            justify="left",
            wraplength=180,
        ).grid(row=1, column=0, padx=14, pady=(0, 12), sticky="w")

        ctk.CTkLabel(
            self.sidebar,
            textvariable=self.session_status_var,
            wraplength=170,
            justify="left",
            text_color="#94b9b2",
        ).grid(row=9, column=0, padx=22, pady=(8, 6), sticky="ew")

        ctk.CTkButton(
            self.sidebar,
            text="Reset Session",
            fg_color="#4e2428",
            hover_color="#6a2d33",
            command=self._reset_session,
        ).grid(row=10, column=0, padx=18, pady=(0, 12), sticky="ew")

        self.sidebar_license_badge = ctk.CTkLabel(
            self.sidebar,
            textvariable=self.license_badge_var,
            fg_color="#173227",
            corner_radius=999,
            padx=12,
            pady=6,
            text_color="#d7f8e3",
        )
        self.sidebar_license_badge.grid(row=11, column=0, padx=18, pady=(0, 20), sticky="w")

        self.content = ctk.CTkFrame(self, fg_color="#0a1118", corner_radius=0)
        self.content.grid(row=0, column=1, sticky="nsew")
        self.content.grid_rowconfigure(1, weight=1)
        self.content.grid_columnconfigure(0, weight=1)

        header = ctk.CTkFrame(self.content, height=112, corner_radius=22, fg_color="#0d1620")
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(1, weight=1)
        header.grid_rowconfigure(0, weight=1)

        header_copy = ctk.CTkFrame(header, fg_color="transparent")
        header_copy.grid(row=0, column=0, padx=28, pady=18, sticky="w")

        self.header_title = ctk.CTkLabel(
            header_copy,
            text="Dashboard",
            font=ctk.CTkFont(size=28, weight="bold"),
            text_color="#dbe8f0",
        )
        self.header_title.grid(row=0, column=0, sticky="w")
        self.header_subtitle = ctk.CTkLabel(
            header_copy,
            textvariable=self.header_context_var,
            text_color="#87a3ad",
            wraplength=560,
            justify="left",
        )
        self.header_subtitle.grid(row=1, column=0, pady=(4, 0), sticky="w")

        header_actions = ctk.CTkFrame(header, fg_color="transparent")
        header_actions.grid(row=0, column=1, padx=18, pady=18, sticky="e")
        if self.header_brand_logo is not None:
            ctk.CTkLabel(
                header_actions,
                text="",
                image=self.header_brand_logo,
                fg_color="#102131",
                corner_radius=14,
                padx=10,
                pady=10,
            ).grid(row=0, column=0, padx=(0, 10), sticky="e")

        self.header_pill = ctk.CTkLabel(
            header_actions,
            textvariable=self.header_badge_var,
            fg_color="#173245",
            corner_radius=999,
            padx=14,
            pady=7,
            text_color="#d8ebf6",
            font=ctk.CTkFont(size=12, weight="bold"),
        )
        self.header_pill.grid(row=0, column=1, sticky="e")

        self.view_host = ctk.CTkFrame(self.content, fg_color="#0a1118")
        self.view_host.grid(row=1, column=0, sticky="nsew", padx=18, pady=18)
        self.view_host.grid_rowconfigure(0, weight=1)
        self.view_host.grid_columnconfigure(0, weight=1)

        self._build_dashboard_view()
        self._build_contacts_view()
        self._build_compose_view()
        self._build_reports_view()
        self._build_settings_view()
        self._build_email_view()
        build_card_creator_view(self)

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
        dialog.configure(fg_color="#091018")
        dialog.protocol("WM_DELETE_WINDOW", self._close_license_dialog_and_exit)

        dialog.grid_columnconfigure(0, weight=1)
        dialog.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(dialog, fg_color="#102131", corner_radius=26)
        header.grid(row=0, column=0, padx=20, pady=(20, 14), sticky="ew")
        header.grid_columnconfigure(1, weight=1)

        crown = ctk.CTkLabel(
            header,
            text="" if self.brand_logo is not None else "MC",
            image=self.brand_logo,
            width=64,
            height=64,
            corner_radius=18,
            fg_color="#c59d3d",
            text_color="#1c1300",
            font=ctk.CTkFont(size=24, weight="bold"),
        )
        crown.grid(row=0, column=0, rowspan=3, padx=(20, 14), pady=20, sticky="n")
        ctk.CTkLabel(
            header,
            text="Trial Expired",
            font=ctk.CTkFont(size=28, weight="bold"),
        ).grid(row=0, column=1, padx=(0, 20), pady=(18, 4), sticky="w")
        ctk.CTkLabel(
            header,
            text="Unlock the premium workspace for persistent sessions, delivery insights, and a cleaner campaign workflow.",
            wraplength=560,
            justify="left",
            text_color="#b8cad6",
        ).grid(row=1, column=1, padx=(0, 20), pady=(0, 10), sticky="w")

        feature_badges = ctk.CTkFrame(header, fg_color="transparent")
        feature_badges.grid(row=2, column=1, padx=(0, 18), pady=(0, 16), sticky="ew")
        for index, label in enumerate(["3-Day Trial", "Session Save", "Delivery Reports", "Premium Dashboard"]):
            ctk.CTkLabel(
                feature_badges,
                text=label,
                fg_color="#1b3950",
                corner_radius=999,
                padx=10,
                pady=4,
                text_color="#dbe9f5",
            ).grid(row=0, column=index, padx=4, pady=4, sticky="w")

        body = ctk.CTkFrame(dialog, fg_color="#0f1822", corner_radius=24)
        body.grid(row=1, column=0, padx=20, pady=(0, 14), sticky="nsew")
        body.grid_columnconfigure(0, weight=3)
        body.grid_columnconfigure(1, weight=2)
        body.grid_rowconfigure(0, weight=1)

        left_panel = ctk.CTkFrame(body, fg_color="#111f2c", corner_radius=20)
        left_panel.grid(row=0, column=0, padx=(18, 10), pady=18, sticky="nsew")
        left_panel.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            left_panel,
            text="Premium Access Includes",
            font=ctk.CTkFont(size=20, weight="bold"),
        ).grid(row=0, column=0, padx=20, pady=(20, 10), sticky="w")
        premium_points = [
            "Saved WhatsApp sessions so QR scans are not repeated on every restart",
            "Delivery and read analytics with CSV/PDF export support",
            "Modern dashboard, compose preview, and reporting workflow",
            "Safer message pacing controls with session reset and activation management",
        ]
        for index, point in enumerate(premium_points, start=1):
            ctk.CTkLabel(
                left_panel,
                text=f"+ {point}",
                justify="left",
                wraplength=360,
                text_color="#9fb5c3",
            ).grid(row=index, column=0, padx=20, pady=6, sticky="w")

        stat_row = ctk.CTkFrame(left_panel, fg_color="transparent")
        stat_row.grid(row=5, column=0, padx=16, pady=(16, 18), sticky="ew")
        for index, (title, value, color) in enumerate([
            ("Session", "48h", "#1b3950"),
            ("Trial", "3 days", "#6b5420"),
            ("Reports", "Live", "#1d4a3c"),
        ]):
            card = ctk.CTkFrame(stat_row, fg_color=color, corner_radius=16)
            card.grid(row=0, column=index, padx=6, sticky="nsew")
            stat_row.grid_columnconfigure(index, weight=1)
            ctk.CTkLabel(card, text=title, text_color="#d5e4ea").pack(anchor="w", padx=12, pady=(10, 2))
            ctk.CTkLabel(card, text=value, font=ctk.CTkFont(size=18, weight="bold")).pack(anchor="w", padx=12, pady=(0, 10))

        right_panel = ctk.CTkFrame(body, fg_color="#0c141c", corner_radius=20)
        right_panel.grid(row=0, column=1, padx=(10, 18), pady=18, sticky="nsew")
        right_panel.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            right_panel,
            text="Activate This Device",
            font=ctk.CTkFont(size=20, weight="bold"),
        ).grid(row=0, column=0, padx=20, pady=(20, 8), sticky="w")
        ctk.CTkLabel(
            right_panel,
            text="Enter your paid passkey below. Activation is stored locally on this device.",
            wraplength=240,
            justify="left",
            text_color="#90a6b3",
        ).grid(row=1, column=0, padx=20, pady=(0, 14), sticky="w")

        ctk.CTkLabel(
            right_panel,
            text="If you close the app without activating, the workspace remains locked until a valid passkey is entered.",
            wraplength=240,
            justify="left",
            text_color="#6eb7d6",
        ).grid(row=2, column=0, padx=20, pady=(0, 18), sticky="w")

        self.license_entry = ctk.CTkEntry(
            right_panel,
            placeholder_text="Enter paid passkey",
            height=44,
            border_width=1,
            fg_color="#101b26",
            border_color="#35566f",
        )
        self.license_entry.grid(row=3, column=0, padx=20, pady=(0, 8), sticky="ew")
        self.license_entry.bind("<Return>", lambda _event: self._submit_license_activation())

        ctk.CTkLabel(
            right_panel,
            textvariable=self.license_message_var,
            text_color="#ff7c87",
            wraplength=240,
            justify="left",
        ).grid(row=4, column=0, padx=20, pady=(0, 12), sticky="w")

        secure_note = ctk.CTkFrame(right_panel, fg_color="#122331", corner_radius=16)
        secure_note.grid(row=5, column=0, padx=20, pady=(0, 14), sticky="ew")
        ctk.CTkLabel(
            secure_note,
            text="Secure local activation",
            font=ctk.CTkFont(size=15, weight="bold"),
        ).pack(anchor="w", padx=14, pady=(12, 4))
        ctk.CTkLabel(
            secure_note,
            text="The passkey is validated inside the app and stored only as local license state on this machine.",
            justify="left",
            wraplength=220,
            text_color="#9fb5c3",
        ).pack(anchor="w", padx=14, pady=(0, 12))

        actions = ctk.CTkFrame(right_panel, fg_color="transparent")
        actions.grid(row=6, column=0, padx=20, pady=(6, 20), sticky="ew")
        actions.grid_columnconfigure(0, weight=1)

        ctk.CTkButton(
            actions,
            text="Exit App",
            fg_color="#5f2d33",
            hover_color="#7d3a42",
            command=self._close_license_dialog_and_exit,
        ).grid(row=0, column=0, padx=(0, 10), sticky="w")
        ctk.CTkButton(
            actions,
            text="Activate Now",
            fg_color="#1c6b4d",
            hover_color="#24895f",
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

    def _build_dashboard_view(self) -> None:
        frame = self._new_view_frame("Dashboard")
        frame.grid_columnconfigure((0, 1), weight=1, uniform="cards")
        frame.grid_rowconfigure(3, weight=1)

        self.dashboard_cards: Dict[str, ctk.CTkLabel] = {}
        self.dashboard_card_meta: Dict[str, ctk.CTkLabel] = {}
        card_specs = [
            ("Sent Today", "0", "#163b34"),
            ("Delivery Rate", "0%", "#1f3f59"),
            ("Active Session", "Checking", "#3e2e18"),
            ("License State", "Trial", "#3d1f3b"),
        ]
        for index, (title, value, color) in enumerate(card_specs):
            card = ctk.CTkFrame(frame, corner_radius=22, fg_color=color, border_width=1, border_color="#314757")
            card.grid(row=index // 2, column=index % 2, padx=10, pady=10, sticky="nsew")
            header = ctk.CTkFrame(card, fg_color="transparent")
            header.pack(fill="x", padx=18, pady=(16, 4))
            ctk.CTkLabel(card, text=title, text_color="#cfe3e4").pack(anchor="w", padx=18, pady=(0, 4))
            ctk.CTkLabel(
                header,
                text="Live KPI",
                fg_color="#0c131b",
                corner_radius=999,
                padx=10,
                pady=5,
                text_color="#dbe8f0",
                font=ctk.CTkFont(size=11, weight="bold"),
            ).pack(side="right")
            label = ctk.CTkLabel(card, text=value, font=ctk.CTkFont(size=30, weight="bold"))
            label.pack(anchor="w", padx=18, pady=(0, 6))
            meta = ctk.CTkLabel(card, text="Awaiting data", text_color="#d6e3e7")
            meta.pack(anchor="w", padx=18, pady=(0, 18))
            self.dashboard_cards[title] = label
            self.dashboard_card_meta[title] = meta

        self.dashboard_license_strip = ctk.CTkFrame(frame, corner_radius=22, fg_color="#121f2c", border_width=1, border_color="#1d3448")
        self.dashboard_license_strip.grid(row=2, column=0, columnspan=2, padx=10, pady=(0, 12), sticky="ew")
        self.dashboard_license_strip.grid_columnconfigure(1, weight=1)
        badge = ctk.CTkLabel(
            self.dashboard_license_strip,
            text="Premium",
            fg_color="#c59d3d",
            text_color="#231700",
            corner_radius=999,
            padx=12,
            pady=6,
            font=ctk.CTkFont(size=12, weight="bold"),
        )
        badge.grid(row=0, column=0, padx=(18, 10), pady=16, sticky="w")
        ctk.CTkLabel(
            self.dashboard_license_strip,
            text="License Status",
            font=ctk.CTkFont(size=18, weight="bold"),
        ).grid(row=0, column=1, padx=(0, 12), pady=16, sticky="w")
        self.dashboard_license_label = ctk.CTkLabel(
            self.dashboard_license_strip,
            textvariable=self.license_status_var,
            text_color="#a7bac6",
            justify="left",
            wraplength=560,
        )
        self.dashboard_license_label.grid(row=0, column=2, padx=12, pady=16, sticky="w")
        self.dashboard_activate_button = ctk.CTkButton(
            self.dashboard_license_strip,
            text="Activate",
            fg_color="#1c6b4d",
            hover_color="#24895f",
            text_color="#d7f8e3",
            text_color_disabled="#9fb5c3",
            command=self._show_license_gate,
        )
        self.dashboard_activate_button.grid(row=0, column=3, padx=18, pady=16, sticky="e")

        activity_frame = ctk.CTkFrame(frame, corner_radius=20, fg_color="#111c27", border_width=1, border_color="#1a2e3f")
        activity_frame.grid(row=3, column=0, columnspan=2, padx=10, pady=(0, 0), sticky="nsew")
        activity_frame.grid_rowconfigure(1, weight=1)
        activity_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(activity_frame, text="Recent Activity", font=ctk.CTkFont(size=18, weight="bold")).grid(
            row=0, column=0, padx=18, pady=(16, 10), sticky="w"
        )
        activity_meta = ctk.CTkFrame(activity_frame, fg_color="transparent")
        activity_meta.grid(row=0, column=0, padx=18, pady=(14, 8), sticky="e")
        ctk.CTkLabel(
            activity_meta,
            textvariable=self.activity_summary_var,
            fg_color="#173245",
            corner_radius=999,
            padx=10,
            pady=5,
            text_color="#d8ebf6",
        ).grid(row=0, column=0, padx=4)
        ctk.CTkLabel(
            activity_meta,
            text="Ops Feed",
            fg_color="#244329",
            corner_radius=999,
            padx=10,
            pady=5,
            text_color="#def2df",
        ).grid(row=0, column=1, padx=4)
        self.activity_text = ctk.CTkTextbox(
            activity_frame,
            fg_color="#0c131b",
            border_width=1,
            border_color="#163144",
            font=ctk.CTkFont(family="Courier New", size=12),
        )
        self.activity_text.grid(row=1, column=0, padx=18, pady=(0, 18), sticky="nsew")
        self._replace_text(self.activity_text, "No activity yet.")

    def _build_contacts_view(self) -> None:
        frame = self._new_view_frame("Contacts")
        frame.grid_rowconfigure(3, weight=1)
        frame.grid_columnconfigure(0, weight=1)

        hero = ctk.CTkFrame(frame, fg_color="#101a24", corner_radius=20, border_width=1, border_color="#183144")
        hero.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        hero.grid_columnconfigure(1, weight=1)

        hero_left = ctk.CTkFrame(hero, fg_color="transparent")
        hero_left.grid(row=0, column=0, padx=18, pady=16, sticky="w")
        ctk.CTkLabel(hero_left, text="Contacts Command Deck", font=ctk.CTkFont(size=22, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(
            hero_left,
            textvariable=self.contacts_search_var,
            text_color="#90aab6",
        ).pack(anchor="w", pady=(4, 0))

        hero_stats = ctk.CTkFrame(hero, fg_color="transparent")
        hero_stats.grid(row=0, column=1, padx=18, pady=16, sticky="e")
        for index, (variable, color) in enumerate([
            (self.contacts_total_var, "#173245"),
            (self.contacts_visible_var, "#244329"),
        ]):
            ctk.CTkLabel(
                hero_stats,
                textvariable=variable,
                fg_color=color,
                corner_radius=999,
                padx=12,
                pady=7,
                text_color="#e0eef5",
            ).grid(row=0, column=index, padx=6)

        toolbar = ctk.CTkFrame(frame, fg_color="#101a24", corner_radius=20, border_width=1, border_color="#183144")
        toolbar.grid_columnconfigure(2, weight=1)
        toolbar.grid(row=1, column=0, sticky="ew", pady=(0, 12))

        ctk.CTkButton(toolbar, text="Import Excel/CSV", command=self._import_contacts).grid(row=0, column=0, padx=14, pady=14)
        ctk.CTkButton(toolbar, text="Refresh", fg_color="#203243", command=self._reload_contacts).grid(row=0, column=1, padx=(0, 14), pady=14)
        search_entry = ctk.CTkEntry(toolbar, textvariable=self.search_var, placeholder_text="Search by name or phone")
        search_entry.grid(row=0, column=2, padx=(0, 14), pady=14, sticky="ew")
        search_entry.bind("<KeyRelease>", lambda _event: self._render_contacts_directory())

        self.contacts_summary_label = ctk.CTkLabel(frame, text="0 contacts loaded", text_color="#8ea5af")
        self.contacts_summary_label.grid(row=2, column=0, sticky="w", padx=6, pady=(0, 10))

        self.contacts_directory = ctk.CTkScrollableFrame(
            frame,
            fg_color="#101a24",
            corner_radius=18,
            border_width=1,
            border_color="#183144",
        )
        self.contacts_directory.grid(row=3, column=0, sticky="nsew")
        self._bind_scrollable_frame_mousewheel(self.contacts_directory)

    def _build_compose_view(self) -> None:
        frame = self._new_view_frame("Compose")
        frame.grid_columnconfigure(0, weight=3)
        frame.grid_columnconfigure(1, weight=2)
        frame.grid_rowconfigure(1, weight=1)

        top = ctk.CTkFrame(frame, fg_color="#101a24", corner_radius=20, border_width=1, border_color="#173041")
        top.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        top.grid_columnconfigure(3, weight=1)

        ctk.CTkLabel(top, text="Template").grid(row=0, column=0, padx=(16, 8), pady=14, sticky="w")
        self.template_menu = ctk.CTkOptionMenu(
            top,
            values=["Custom Message"],
            variable=self.template_var,
            command=self._on_template_selected,
            fg_color="#173245",
            button_color="#1d3545",
            button_hover_color="#203243",
            text_color="#d8ebf6",
            dropdown_fg_color="#101a24",
            dropdown_hover_color="#203243",
            dropdown_text_color="#dbe8f0",
        )
        self.template_menu.grid(row=0, column=1, padx=(0, 12), pady=14, sticky="w")
        ctk.CTkCheckBox(top, text="Select all contacts", variable=self.select_all_var, command=self._toggle_select_all).grid(
            row=0, column=2, padx=(0, 12), pady=14, sticky="w"
        )
        ctk.CTkCheckBox(top, text="Consent confirmed", variable=self.consent_confirmed_var).grid(
            row=0, column=3, padx=(0, 16), pady=14, sticky="e"
        )

        compose_meta = ctk.CTkFrame(top, fg_color="transparent")
        compose_meta.grid(row=1, column=0, columnspan=4, padx=16, pady=(0, 14), sticky="ew")
        self.compose_contacts_chip = ctk.CTkLabel(
            compose_meta,
            textvariable=self.compose_contacts_var,
            fg_color="#173245",
            corner_radius=999,
            padx=12,
            pady=6,
            text_color="#d8ebf6",
        )
        self.compose_contacts_chip.grid(row=0, column=0, padx=(0, 8), sticky="w")
        self.compose_delay_chip = ctk.CTkLabel(
            compose_meta,
            textvariable=self.compose_delay_var,
            fg_color="#244329",
            corner_radius=999,
            padx=12,
            pady=6,
            text_color="#def2df",
        )
        self.compose_delay_chip.grid(row=0, column=1, padx=8, sticky="w")
        self.compose_limit_chip = ctk.CTkLabel(
            compose_meta,
            textvariable=self.compose_limit_var,
            fg_color="#4a3318",
            corner_radius=999,
            padx=12,
            pady=6,
            text_color="#ffe4b5",
        )
        self.compose_limit_chip.grid(row=0, column=2, padx=8, sticky="w")

        editor_frame = ctk.CTkFrame(frame, fg_color="#101a24", corner_radius=20, border_width=1, border_color="#173041")
        editor_frame.grid(row=1, column=0, sticky="nsew", padx=(0, 10))
        editor_frame.grid_columnconfigure(0, weight=1)
        editor_frame.grid_rowconfigure(2, weight=1)
        editor_frame.grid_rowconfigure(4, weight=1)

        ctk.CTkLabel(editor_frame, text="Message Editor", font=ctk.CTkFont(size=18, weight="bold")).grid(
            row=0, column=0, padx=18, pady=(16, 8), sticky="w"
        )
        ctk.CTkLabel(
            editor_frame,
            text="Campaign Console",
            text_color="#6faed2",
            font=ctk.CTkFont(size=12, weight="bold"),
        ).grid(row=0, column=0, padx=18, pady=(18, 8), sticky="e")

        variables_row = ctk.CTkFrame(editor_frame, fg_color="transparent")
        variables_row.grid(row=1, column=0, padx=14, pady=(0, 10), sticky="ew")
        for index, variable in enumerate(["{name}", "{amount}", "{date}", "{phone}"]):
            ctk.CTkButton(
                variables_row,
                text=variable,
                width=90,
                fg_color="#1d3545",
                command=lambda token=variable: self._insert_variable(token),
            ).grid(row=0, column=index, padx=4, pady=4)

        self.message_textbox = ctk.CTkTextbox(editor_frame, fg_color="#0c131b", wrap="word")
        self.message_textbox.grid(row=2, column=0, padx=18, pady=(0, 14), sticky="nsew")
        self.message_textbox.bind("<KeyRelease>", lambda _event: self._refresh_preview())

        ctk.CTkLabel(editor_frame, text="Contacts", font=ctk.CTkFont(size=18, weight="bold")).grid(
            row=3, column=0, padx=18, pady=(0, 8), sticky="w"
        )
        self.compose_contacts_frame = ctk.CTkScrollableFrame(editor_frame, fg_color="#0c131b", corner_radius=14)
        self.compose_contacts_frame.grid(row=4, column=0, padx=18, pady=(0, 18), sticky="nsew")
        self._bind_scrollable_frame_mousewheel(self.compose_contacts_frame)

        preview_frame = ctk.CTkFrame(frame, fg_color="#101a24", corner_radius=20, border_width=1, border_color="#173041")
        preview_frame.grid(row=1, column=1, sticky="nsew")
        preview_frame.grid_rowconfigure(2, weight=1)
        preview_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(preview_frame, text="Preview", font=ctk.CTkFont(size=18, weight="bold")).grid(
            row=0, column=0, padx=18, pady=(16, 8), sticky="w"
        )
        preview_chips = ctk.CTkFrame(preview_frame, fg_color="transparent")
        preview_chips.grid(row=0, column=0, padx=18, pady=(14, 8), sticky="e")
        ctk.CTkLabel(
            preview_chips,
            text="Live Render",
            fg_color="#173245",
            corner_radius=999,
            padx=10,
            pady=5,
            text_color="#d8ebf6",
        ).grid(row=0, column=0, padx=4)
        ctk.CTkLabel(
            preview_chips,
            text="First 3 Contacts",
            fg_color="#244329",
            corner_radius=999,
            padx=10,
            pady=5,
            text_color="#def2df",
        ).grid(row=0, column=1, padx=4)
        ctk.CTkLabel(preview_frame, text="Preview for the first 3 selected contacts", text_color="#8ea5af").grid(
            row=1, column=0, padx=18, pady=(0, 8), sticky="w"
        )
        self.preview_text = ctk.CTkTextbox(preview_frame, fg_color="#0c131b", wrap="word")
        self.preview_text.grid(row=2, column=0, padx=18, pady=(0, 18), sticky="nsew")

        controls = ctk.CTkFrame(frame, fg_color="#101a24", corner_radius=20, border_width=1, border_color="#173041")
        controls.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(12, 0))
        controls.grid_columnconfigure(3, weight=1)

        ctk.CTkButton(controls, text="Start", fg_color="#1c6b4d", hover_color="#24895f", command=self._start_sending).grid(
            row=0, column=0, padx=(16, 8), pady=14
        )
        ctk.CTkButton(controls, text="Pause / Resume", fg_color="#7a5825", hover_color="#9a6f30", command=self._toggle_pause).grid(
            row=0, column=1, padx=8, pady=14
        )
        ctk.CTkButton(controls, text="Stop", fg_color="#7d3037", hover_color="#a23e46", command=self._stop_sending).grid(
            row=0, column=2, padx=8, pady=14
        )
        self.compose_progress = ctk.CTkProgressBar(controls)
        self.compose_progress.grid(row=0, column=3, padx=(12, 12), pady=14, sticky="ew")
        self.compose_progress.set(0)
        self.compose_progress.configure(progress_color="#39b37a")
        ctk.CTkLabel(controls, textvariable=self.progress_status_var).grid(row=0, column=4, padx=(0, 16), pady=14, sticky="e")

    def _build_reports_view(self) -> None:
        frame = self._new_view_frame("Reports")
        frame.grid_rowconfigure(3, weight=1)
        frame.grid_columnconfigure(0, weight=1)

        hero = ctk.CTkFrame(frame, fg_color="#101a24", corner_radius=20, border_width=1, border_color="#183144")
        hero.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        hero.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(hero, text="Reports Intelligence Deck", font=ctk.CTkFont(size=22, weight="bold")).grid(
            row=0, column=0, padx=18, pady=(16, 4), sticky="w"
        )
        ctk.CTkLabel(
            hero,
            textvariable=self.reports_feed_var,
            text_color="#90aab6",
        ).grid(row=1, column=0, padx=18, pady=(0, 16), sticky="w")
        ctk.CTkLabel(
            hero,
            text="Live Monitoring",
            fg_color="#173245",
            corner_radius=999,
            padx=12,
            pady=6,
            text_color="#d8ebf6",
        ).grid(row=0, column=1, rowspan=2, padx=18, pady=16, sticky="e")

        stats_strip = ctk.CTkFrame(frame, fg_color="#101a24", corner_radius=20, border_width=1, border_color="#183144")
        stats_strip.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        blocks = [
            ("Sent", self.sent_count_var),
            ("Delivered", self.delivered_count_var),
            ("Read", self.read_count_var),
            ("Failed", self.failed_count_var),
        ]
        for index, (title, variable) in enumerate(blocks):
            stats_strip.grid_columnconfigure(index, weight=1)
            block = ctk.CTkFrame(stats_strip, fg_color="#0c131b", corner_radius=16, border_width=1, border_color="#163144")
            block.grid(row=0, column=index, padx=10, pady=12, sticky="nsew")
            ctk.CTkLabel(block, text=title, text_color="#8ea5af").pack(anchor="w", padx=12, pady=(10, 2))
            ctk.CTkLabel(block, textvariable=variable, font=ctk.CTkFont(size=22, weight="bold")).pack(anchor="w", padx=12, pady=(0, 10))
            ctk.CTkLabel(block, text="Live", text_color="#6faed2", font=ctk.CTkFont(size=11, weight="bold")).pack(
                anchor="w", padx=12, pady=(0, 10)
            )

        rate_frame = ctk.CTkFrame(frame, fg_color="#101a24", corner_radius=20, border_width=1, border_color="#183144")
        rate_frame.grid(row=2, column=0, sticky="ew", pady=(0, 12))
        rate_frame.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(rate_frame, text="Delivery Rate", font=ctk.CTkFont(size=18, weight="bold")).grid(
            row=0, column=0, padx=16, pady=16, sticky="w"
        )
        ctk.CTkLabel(
            rate_frame,
            text="Analytics Stream",
            fg_color="#173245",
            corner_radius=999,
            padx=12,
            pady=6,
            text_color="#d8ebf6",
        ).grid(row=0, column=2, padx=(0, 12), pady=16, sticky="e")
        self.delivery_progress = ctk.CTkProgressBar(rate_frame)
        self.delivery_progress.grid(row=0, column=1, padx=10, pady=16, sticky="ew")
        self.delivery_progress.set(0)
        self.delivery_progress.configure(progress_color="#39b37a")
        ctk.CTkLabel(rate_frame, textvariable=self.delivery_rate_var).grid(row=0, column=3, padx=16, pady=16, sticky="e")

        body = ctk.CTkFrame(frame, fg_color="#101a24", corner_radius=20, border_width=1, border_color="#183144")
        body.grid(row=3, column=0, sticky="nsew")
        body.grid_rowconfigure(3, weight=1)
        body.grid_columnconfigure(0, weight=1)

        actions = ctk.CTkFrame(body, fg_color="transparent")
        actions.grid(row=0, column=0, sticky="ew", padx=14, pady=(14, 8))
        actions.grid_columnconfigure(4, weight=1)
        ctk.CTkLabel(actions, text="Export Format").grid(row=0, column=0, padx=(0, 8), pady=8)
        ctk.CTkOptionMenu(
            actions,
            values=["csv", "pdf"],
            variable=self.report_format_var,
            command=lambda _value: self._update_report_summary(),
            fg_color="#173245",
            button_color="#1d3545",
            button_hover_color="#203243",
            text_color="#d8ebf6",
            dropdown_fg_color="#101a24",
            dropdown_hover_color="#203243",
            dropdown_text_color="#dbe8f0",
        ).grid(row=0, column=1, padx=(0, 12), pady=8)
        ctk.CTkButton(actions, text="Export Report", command=self._export_report).grid(row=0, column=2, pady=8)
        ctk.CTkLabel(
            actions,
            text="Executive Report Deck",
            text_color="#7fa9bf",
            font=ctk.CTkFont(size=12, weight="bold"),
        ).grid(row=0, column=3, padx=(14, 0), pady=8, sticky="e")
        ctk.CTkLabel(
            actions,
            textvariable=self.report_export_status_var,
            fg_color="#122331",
            corner_radius=999,
            padx=12,
            pady=6,
            text_color="#d8ebf6",
        ).grid(row=0, column=4, padx=(14, 0), pady=8, sticky="e")

        insights = ctk.CTkFrame(body, fg_color="#0c131b", corner_radius=18, border_width=1, border_color="#163144")
        insights.grid(row=1, column=0, padx=18, pady=(0, 12), sticky="ew")
        insights.grid_columnconfigure((0, 1, 2), weight=1)
        for index, (title, value, color) in enumerate([
            ("Pipeline", "Tracked", "#173245"),
            ("Export", "CSV / PDF", "#244329"),
            ("State", "Live Feed", "#4a3318"),
        ]):
            tile = ctk.CTkFrame(insights, fg_color=color, corner_radius=16)
            tile.grid(row=0, column=index, padx=8, pady=10, sticky="ew")
            ctk.CTkLabel(tile, text=title, text_color="#d3e2ea").pack(anchor="w", padx=12, pady=(10, 2))
            ctk.CTkLabel(tile, text=value, font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", padx=12, pady=(0, 10))

        ctk.CTkLabel(body, text="Recent Delivery Activity", font=ctk.CTkFont(size=18, weight="bold")).grid(
            row=2, column=0, padx=18, pady=(4, 8), sticky="w"
        )
        self.reports_text = ctk.CTkTextbox(
            body,
            fg_color="#0c131b",
            border_width=1,
            border_color="#163144",
            font=ctk.CTkFont(family="Courier New", size=12),
        )
        self.reports_text.grid(row=3, column=0, padx=18, pady=(0, 18), sticky="nsew")
        self._replace_text(self.reports_text, "No tracked messages yet.")

    def _build_settings_view(self) -> None:
        frame = self._new_view_container("Settings", scrollable=True)
        frame.grid_columnconfigure((0, 1), weight=1, uniform="settings")

        hero = ctk.CTkFrame(frame, fg_color="#101a24", corner_radius=20, border_width=1, border_color="#183144")
        hero.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        hero.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(hero, text="Settings Control Center", font=ctk.CTkFont(size=22, weight="bold")).grid(
            row=0, column=0, padx=18, pady=(16, 4), sticky="w"
        )
        ctk.CTkLabel(
            hero,
            text="Tune cadence, session safety, appearance, and device activation from one place.",
            text_color="#90aab6",
        ).grid(row=1, column=0, padx=18, pady=(0, 16), sticky="w")
        hero_chips = ctk.CTkFrame(hero, fg_color="transparent")
        hero_chips.grid(row=0, column=1, rowspan=2, padx=18, pady=16, sticky="e")
        for index, variable in enumerate([self.settings_delay_chip_var, self.settings_theme_chip_var, self.settings_guard_chip_var]):
            ctk.CTkLabel(
                hero_chips,
                textvariable=variable,
                fg_color="#173245" if index == 0 else "#244329" if index == 1 else "#4a3318",
                corner_radius=999,
                padx=12,
                pady=6,
                text_color="#e0eef5",
            ).grid(row=0, column=index, padx=6)

        card = ctk.CTkFrame(frame, fg_color="#101a24", corner_radius=20, border_width=1, border_color="#183144")
        card.grid(row=1, column=0, sticky="nsew", padx=(0, 8))
        card.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(card, text="Campaign Safety", font=ctk.CTkFont(size=18, weight="bold")).grid(
            row=0, column=0, columnspan=3, padx=18, pady=(18, 6), sticky="w"
        )
        ctk.CTkLabel(card, text="Rate limits and guardrails for stable sending.", text_color="#8ea5af").grid(
            row=1, column=0, columnspan=3, padx=18, pady=(0, 16), sticky="w"
        )

        ctk.CTkLabel(card, text="Delay between messages").grid(row=2, column=0, padx=18, pady=10, sticky="w")
        self.delay_slider = ctk.CTkSlider(card, from_=10, to=120, number_of_steps=110, command=self._on_delay_change)
        self.delay_slider.grid(row=2, column=1, padx=18, pady=10, sticky="ew")
        self.delay_slider.set(self.delay_var.get())
        self.delay_label = ctk.CTkLabel(card, text=f"{self.delay_var.get()} sec")
        self.delay_label.grid(row=2, column=2, padx=(0, 18), pady=10, sticky="e")

        ctk.CTkLabel(card, text="Daily limit").grid(row=3, column=0, padx=18, pady=10, sticky="w")
        self.limit_slider = ctk.CTkSlider(card, from_=10, to=500, number_of_steps=98, command=self._on_daily_limit_change)
        self.limit_slider.grid(row=3, column=1, padx=18, pady=10, sticky="ew")
        self.limit_slider.set(self.daily_limit_var.get())
        self.limit_label = ctk.CTkLabel(card, text=str(self.daily_limit_var.get()))
        self.limit_label.grid(row=3, column=2, padx=(0, 18), pady=10, sticky="e")

        self.limit_warning_label = ctk.CTkLabel(card, text="", text_color="#e5c07b")
        self.limit_warning_label.grid(row=4, column=1, padx=18, pady=(0, 10), sticky="w")

        ctk.CTkSwitch(card, text="Random jitter", variable=self.jitter_var, command=self._save_settings).grid(
            row=5, column=0, padx=18, pady=10, sticky="w"
        )
        ctk.CTkSwitch(card, text="Consent required", variable=self.consent_required_var, command=self._save_settings).grid(
            row=5, column=1, padx=18, pady=10, sticky="w"
        )

        system_card = ctk.CTkFrame(frame, fg_color="#101a24", corner_radius=20, border_width=1, border_color="#183144")
        system_card.grid(row=1, column=1, sticky="nsew", padx=(8, 0))
        system_card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(system_card, text="System Experience", font=ctk.CTkFont(size=18, weight="bold")).grid(
            row=0, column=0, padx=18, pady=(18, 6), sticky="w"
        )
        ctk.CTkLabel(system_card, text="Theme, session state, and workspace recovery controls.", text_color="#8ea5af").grid(
            row=1, column=0, padx=18, pady=(0, 16), sticky="w"
        )
        ctk.CTkLabel(system_card, text="Theme selector").grid(row=2, column=0, padx=18, pady=(0, 8), sticky="w")
        ctk.CTkOptionMenu(
            system_card,
            values=["Dark", "Light", "System"],
            variable=self.theme_var,
            command=self._on_theme_selected,
            fg_color="#173245",
            button_color="#1d3545",
            button_hover_color="#203243",
            text_color="#d8ebf6",
            dropdown_fg_color="#101a24",
            dropdown_hover_color="#203243",
            dropdown_text_color="#dbe8f0",
        ).grid(
            row=3, column=0, padx=18, pady=(0, 14), sticky="w"
        )
        session_strip = ctk.CTkFrame(system_card, fg_color="#0c131b", corner_radius=16, border_width=1, border_color="#163144")
        session_strip.grid(row=4, column=0, padx=18, pady=(0, 14), sticky="ew")
        ctk.CTkLabel(session_strip, text="Session Status", font=ctk.CTkFont(size=15, weight="bold")).pack(anchor="w", padx=14, pady=(12, 4))
        ctk.CTkLabel(session_strip, textvariable=self.session_status_var, text_color="#8ea5af", wraplength=360, justify="left").pack(
            anchor="w", padx=14, pady=(0, 12)
        )
        ctk.CTkButton(system_card, text="Reset Session", fg_color="#7d3037", hover_color="#a23e46", command=self._reset_session).grid(
            row=5, column=0, padx=18, pady=(0, 18), sticky="w"
        )

        license_card = ctk.CTkFrame(frame, fg_color="#101a24", corner_radius=20, border_width=1, border_color="#183144")
        license_card.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(14, 0))
        license_card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            license_card,
            text="License & Activation",
            font=ctk.CTkFont(size=18, weight="bold"),
        ).grid(row=0, column=0, padx=18, pady=(18, 8), sticky="w")
        self.settings_license_label = ctk.CTkLabel(
            license_card,
            textvariable=self.license_status_var,
            text_color="#9db1bd",
            justify="left",
            wraplength=700,
        )
        self.settings_license_label.grid(row=1, column=0, padx=18, pady=(0, 14), sticky="w")

        premium_strip = ctk.CTkFrame(license_card, fg_color="#122331", corner_radius=16)
        premium_strip.grid(row=2, column=0, padx=18, pady=(0, 14), sticky="ew")
        premium_strip.grid_columnconfigure((0, 1, 2), weight=1)
        for index, (title, value) in enumerate([
            ("Plan", "Premium"),
            ("Session", "Persistent"),
            ("Reports", "Export Ready"),
        ]):
            tile = ctk.CTkFrame(premium_strip, fg_color="#173245", corner_radius=14)
            tile.grid(row=0, column=index, padx=8, pady=10, sticky="ew")
            ctk.CTkLabel(tile, text=title, text_color="#a9c0cd").pack(anchor="w", padx=12, pady=(10, 2))
            ctk.CTkLabel(tile, text=value, font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", padx=12, pady=(0, 10))

        license_actions = ctk.CTkFrame(license_card, fg_color="transparent")
        license_actions.grid(row=3, column=0, padx=18, pady=(0, 18), sticky="ew")
        license_actions.grid_columnconfigure(1, weight=1)
        self.settings_activate_button = ctk.CTkButton(
            license_actions,
            text="Activate License",
            fg_color="#1c6b4d",
            hover_color="#24895f",
            text_color="#d7f8e3",
            text_color_disabled="#9fb5c3",
            command=self._show_license_gate,
        )
        self.settings_activate_button.grid(row=0, column=0, padx=(0, 10), sticky="w")
        self.settings_deactivate_button = ctk.CTkButton(
            license_actions,
            text="Deactivate License",
            fg_color="#5f2d33",
            hover_color="#7d3a42",
            text_color="#ffd3d8",
            text_color_disabled="#9fb5c3",
            command=self._deactivate_license,
        )
        self.settings_deactivate_button.grid(row=0, column=1, padx=(0, 10), sticky="w")
        self.settings_license_chip = ctk.CTkLabel(
            license_actions,
            textvariable=self.license_badge_var,
            fg_color="#173227",
            corner_radius=999,
            padx=12,
            pady=6,
            text_color="#d7f8e3",
        )
        self.settings_license_chip.grid(row=0, column=2, sticky="e")

        self._update_settings_summary()
        self._update_daily_limit_warning()

    def _new_view_frame(self, name: str) -> ctk.CTkFrame:
        return self._new_view_container(name)

    def _new_view_container(self, name: str, scrollable: bool = False) -> ctk.CTkFrame:
        frame_class = ctk.CTkScrollableFrame if scrollable else ctk.CTkFrame
        frame = frame_class(self.view_host, fg_color="#0a1118", corner_radius=0)
        self.view_frames[name] = frame
        container = getattr(frame, "_parent_frame", frame)
        container.grid(row=0, column=0, sticky="nsew")
        container.grid_remove()
        self.view_containers[name] = container
        if scrollable:
            self._bind_scrollable_frame_mousewheel(frame)
        return frame

    def _show_view(self, view_name: str) -> None:
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
                fg_color="#173245" if is_active else "transparent",
                hover_color="#244329" if is_active else "#203243",
                border_color="#173245" if is_active else "#183144",
                text_color="#d8ebf6" if is_active else "#a7bac6",
            )
        if view_name in {"Compose", "Reports", "Dashboard"}:
            self._refresh_stats()
        if view_name == "Compose":
            self._refresh_preview()

    def _apply_view_chrome(self, view_name: str) -> None:
        view_meta = {
            "Dashboard": (
                "Persistent WhatsApp sessions, delivery analytics, and safer campaigns.",
                "Enterprise Messaging Suite",
            ),
            "Contacts": (
                "Organize your outreach directory with searchable, campaign-ready contact records.",
                "Contacts Command Deck",
            ),
            "Compose": (
                "Build personalized campaigns with live preview, pacing controls, and contact-aware messaging.",
                "Campaign Console",
            ),
            "Reports": (
                "Track sent, delivered, and read performance from a live executive monitoring workspace.",
                "Reports Intelligence",
            ),
            "Email": (
            "Send HTML email campaigns with templates and variable substitution.",
            "Email Campaign Center",
        ),
        "Cards": (
            "Build beautiful marketing cards for any app — WhatsApp, email, social.",
            "Card Creator Studio",
        ),
        "Settings": (          
                "Tune cadence, safety guardrails, themes, sessions, and device activation from one premium control center.",
                "Control Center Settings",
            ),
        }
        subtitle, badge = view_meta.get(view_name, view_meta["Dashboard"])
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

    def _save_settings(self) -> None:
        self.db.set_setting_json(
            self.SETTINGS_KEY,
            {
                "theme": self.theme_var.get(),
                "delay": self.delay_var.get(),
                "daily_limit": self.daily_limit_var.get(),
                "jitter": self.jitter_var.get(),
                "consent_required": self.consent_required_var.get(),
            },
        )
        self._update_settings_summary()
        self._refresh_stats()

    def _apply_theme(self, selected_theme: str) -> None:
        ctk.set_appearance_mode(selected_theme)
        ctk.set_default_color_theme("green")
        if hasattr(self, "view_host"):
            self._sync_theme_overrides()
            self.after_idle(self._sync_theme_overrides)

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
            badge_color = "#6b5420"
            badge_text_color = "#ffe7b3"
            activate_state = "normal"
            deactivate_state = "disabled"
            card_value = badge_text
        elif info.get("is_valid"):
            badge_text = "Licensed"
            badge_color = "#173227"
            badge_text_color = "#d7f8e3"
            activate_state = "disabled"
            deactivate_state = "normal"
            card_value = "Paid"
        else:
            badge_text = "Activation Required"
            badge_color = "#5f2d33"
            badge_text_color = "#ffd3d8"
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
        self._refresh_stats()

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

    def _render_contacts_directory(self) -> None:
        for child in self.contacts_directory.winfo_children():
            child.destroy()

        query = self.search_var.get().strip().lower()
        results = [
            contact for contact in self.contacts
            if not query or query in contact.phone.lower() or query in (contact.name or "").lower()
        ]
        self._update_contacts_summary(len(results), query)
        if not results:
            empty = ctk.CTkFrame(self.contacts_directory, fg_color="#0c131b", corner_radius=18, border_width=1, border_color="#183144")
            empty.pack(fill="x", padx=8, pady=8)
            ctk.CTkLabel(empty, text="No contacts found", font=ctk.CTkFont(size=17, weight="bold")).pack(padx=18, pady=(18, 4), anchor="w")
            ctk.CTkLabel(
                empty,
                text="Adjust your search or import a fresh CSV/Excel list to continue.",
                text_color="#8ea5af",
            ).pack(padx=18, pady=(0, 18), anchor="w")
            self._bind_scrollable_frame_mousewheel(self.contacts_directory)
            self._sync_widget_theme(self.contacts_directory)
            return

        for contact in results:
            card = ctk.CTkFrame(self.contacts_directory, fg_color="#0c131b", corner_radius=18, border_width=1, border_color="#163144")
            card.pack(fill="x", padx=6, pady=6)
            top = ctk.CTkFrame(card, fg_color="transparent")
            top.pack(fill="x", padx=14, pady=(12, 4))
            ctk.CTkLabel(top, text=contact.name or "Unnamed Contact", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", side="left")
            ctk.CTkLabel(
                top,
                text="Directory",
                fg_color="#173245",
                corner_radius=999,
                padx=10,
                pady=5,
                text_color="#d8ebf6",
                font=ctk.CTkFont(size=11, weight="bold"),
            ).pack(anchor="e", side="right")
            ctk.CTkLabel(card, text=contact.phone, text_color="#8ea5af").pack(anchor="w", padx=14, pady=(0, 4))
            footer = ctk.CTkFrame(card, fg_color="transparent")
            footer.pack(fill="x", padx=14, pady=(0, 12))
            ctk.CTkLabel(
                footer,
                text=f"Contact ID {contact.id if contact.id is not None else 'Pending'}",
                text_color="#6f8796",
            ).pack(side="left")
            ctk.CTkLabel(
                footer,
                text="Ready for campaign",
                text_color="#7dc59b",
                font=ctk.CTkFont(size=11, weight="bold"),
            ).pack(side="right")

        self._bind_scrollable_frame_mousewheel(self.contacts_directory)
        self._sync_widget_theme(self.contacts_directory)

    def _render_compose_contacts(self) -> None:
        for child in self.compose_contacts_frame.winfo_children():
            child.destroy()

        if not self.contacts:
            ctk.CTkLabel(self.compose_contacts_frame, text="Import contacts to start composing.", text_color="#8ea5af").pack(
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
            filetypes=[("Excel and CSV", "*.xlsx *.xls *.csv"), ("All files", "*.*")],
        )
        if not file_path:
            return
        imported_count, errors = self.contact_manager.import_from_file(file_path)
        self._reload_contacts()
        if errors:
            messagebox.showwarning("Import completed with warnings", f"Imported {imported_count} contacts\n\n" + "\n".join(errors[:10]))
        else:
            messagebox.showinfo("Contacts Imported", f"Imported {imported_count} contacts successfully.")
        self._log_activity(f"Imported {imported_count} contacts from {Path(file_path).name}")

    def _start_session_bootstrap(self) -> None:
        if self.license_locked:
            return

        def worker() -> None:
            self._set_session_status("Launching WhatsApp session...")
            try:
                state = self.whatsapp_sender.initialize()
                self._set_session_status(state.status_text)
                self._log_activity(state.status_text)
                self.after(0, self._refresh_stats)
            except Exception as exc:
                Logger.warning(f"Session bootstrap failed: {exc}")
                self._set_session_status("Session expired - please scan QR")
                self._log_activity(f"Session bootstrap failed: {exc}")

        threading.Thread(target=worker, daemon=True).start()

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
                self.after(0, self._refresh_stats)

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
        self._refresh_stats()

    def _refresh_stats(self) -> None:
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
        self.delivery_progress.set(min(max(delivery_rate / 100.0, 0.0), 1.0))
        self.reports_feed_var.set(
            f"{sent_count} sent, {delivered_count} delivered, {read_count} read, {failed_count} failed"
        )
        self._update_report_summary()

        session_state = self.whatsapp_sender.get_session_state()
        self.dashboard_cards["Sent Today"].configure(text=str(sent_count))
        self.dashboard_cards["Delivery Rate"].configure(text=f"{delivery_rate:.1f}%")
        self.dashboard_cards["Active Session"].configure(text="Active" if session_state.is_active else "Scan QR")
        self.dashboard_card_meta["Sent Today"].configure(text=f"{len(self._get_selected_contacts())} contacts armed")
        self.dashboard_card_meta["Delivery Rate"].configure(text=f"Delivered {delivered_count} | Read {read_count}")
        self.dashboard_card_meta["Active Session"].configure(text=session_state.status_text)
        self._update_license_ui()
        self._set_session_status(session_state.status_text)
        self.activity_summary_var.set(f"{min(len(self.activity_items), 20)} recent events")

        recent_messages = self.whatsapp_sender.get_recent_activity(limit=12)
        rows = [
            f"[{str(row.get('status', 'unknown')).upper():<10}] {row.get('phone')}   #{row.get('id')}   {row.get('sent_at') or row.get('created_at')}"
            for row in recent_messages
        ]
        self._replace_text(self.reports_text, "\n".join(rows) if rows else "No tracked messages yet.")
        self._replace_text(self.activity_text, "\n".join(self.activity_items[:20]) if self.activity_items else "No activity yet.")

    def _export_report(self) -> None:
        try:
            output_path = self.whatsapp_sender.export_report(self.report_format_var.get())
            self._log_activity(f"Report exported to {output_path.name}")
            messagebox.showinfo("Report Exported", f"Saved report to:\n{output_path}")
            self._refresh_stats()
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
        self._refresh_stats()
        self.after(5000, self._periodic_refresh)

    def _build_email_view(self) -> None:
        """Bulk Email Campaign view — full CustomTkinter UI matching app style."""

        frame = self._new_view_container("Email", scrollable=False)
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_columnconfigure(1, weight=2)
        frame.grid_rowconfigure(1, weight=1)

        # ── Header bar ────────────────────────────────────────────────────────────
        hero = ctk.CTkFrame(frame, fg_color="#101a24", corner_radius=20,
                            border_width=1, border_color="#183144")
        hero.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        hero.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(hero, text="Email Campaign Center",
                     font=ctk.CTkFont(size=22, weight="bold")).grid(
            row=0, column=0, padx=18, pady=(16, 4), sticky="w")
        ctk.CTkLabel(hero,
                     text="Send personalized HTML email campaigns — Gmail, Outlook, or any SMTP server",
                     text_color="#90aab6").grid(
            row=1, column=0, padx=18, pady=(0, 16), sticky="w")

        badge_frame = ctk.CTkFrame(hero, fg_color="transparent")
        badge_frame.grid(row=0, column=1, rowspan=2, padx=18, pady=16, sticky="e")
        for i, (txt, col) in enumerate([("SMTP Ready", "#173245"),
                                         ("HTML Templates", "#244329"),
                                         ("Variable Support", "#4a3318")]):
            ctk.CTkLabel(badge_frame, text=txt, fg_color=col, corner_radius=999,
                         padx=12, pady=6, text_color="#e0eef5").grid(
                row=0, column=i, padx=5)

        # ── LEFT panel ────────────────────────────────────────────────────────────
        left_scroll = ctk.CTkScrollableFrame(frame, fg_color="#0a1118", corner_radius=0)
        left_scroll.grid(row=1, column=0, sticky="nsew", padx=(0, 8))
        left_scroll.grid_columnconfigure(0, weight=1)

        # SMTP Settings card
        smtp_card = ctk.CTkFrame(left_scroll, fg_color="#101a24", corner_radius=20,
                                  border_width=1, border_color="#173041")
        smtp_card.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        smtp_card.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(smtp_card, text="📮  SMTP Settings",
                     font=ctk.CTkFont(size=18, weight="bold")).grid(
            row=0, column=0, columnspan=2, padx=18, pady=(16, 8), sticky="w")

        PRESETS = {
            "Gmail":   ("smtp.gmail.com", "587"),
            "Outlook": ("smtp-mail.outlook.com", "587"),
            "Yahoo":   ("smtp.mail.yahoo.com", "587"),
            "Custom":  ("", "587"),
        }

        self._em_provider  = ctk.StringVar(value="Gmail")
        self._em_host      = ctk.StringVar(value="smtp.gmail.com")
        self._em_port      = ctk.StringVar(value="587")
        self._em_user      = ctk.StringVar()
        self._em_pass      = ctk.StringVar()
        self._em_from_name = ctk.StringVar(value="My Business")
        self._em_from_addr = ctk.StringVar()
        self._em_delay     = ctk.StringVar(value="5")

        def on_preset(val):
            h, p = PRESETS.get(val, ("", "587"))
            self._em_host.set(h)
            self._em_port.set(p)

        ctk.CTkLabel(smtp_card, text="Provider").grid(
            row=1, column=0, padx=18, pady=5, sticky="w")
        ctk.CTkOptionMenu(smtp_card, values=list(PRESETS.keys()),
                          variable=self._em_provider, command=on_preset,
                          fg_color="#173245", button_color="#1d3545",
                          button_hover_color="#203243", text_color="#d8ebf6",
                          dropdown_fg_color="#101a24",
                          dropdown_hover_color="#203243",
                          dropdown_text_color="#dbe8f0").grid(
            row=1, column=1, padx=(4, 18), pady=5, sticky="ew")

        for i, (lbl, var, secret) in enumerate([
            ("Host",         self._em_host,      False),
            ("Port",         self._em_port,      False),
            ("Username",     self._em_user,      False),
            ("Password",     self._em_pass,      True),
            ("Sender Name",  self._em_from_name, False),
            ("Sender Email", self._em_from_addr, False),
            ("Delay (sec)",  self._em_delay,     False),
        ], start=2):
            ctk.CTkLabel(smtp_card, text=lbl).grid(
                row=i, column=0, padx=18, pady=5, sticky="w")
            ctk.CTkEntry(smtp_card, textvariable=var,
                         show="●" if secret else "",
                         fg_color="#0c131b", border_color="#173041").grid(
                row=i, column=1, padx=(4, 18), pady=5, sticky="ew")

        def test_connection():
            try:
                conn = smtplib.SMTP(self._em_host.get(), int(self._em_port.get()))
                conn.starttls(context=ssl.create_default_context())
                conn.login(self._em_user.get(), self._em_pass.get())
                conn.quit()
                messagebox.showinfo("Success ✅", "SMTP connection successful!")
            except smtplib.SMTPAuthenticationError:
                messagebox.showerror("Auth Failed",
                    "Wrong username/password.\nFor Gmail use an App Password.")
            except Exception as ex:
                messagebox.showerror("Connection Failed", str(ex))

        ctk.CTkButton(smtp_card, text="🔌  Test Connection",
                      fg_color="#1c6b4d", hover_color="#24895f",
                      command=test_connection).grid(
            row=9, column=0, columnspan=2, padx=18, pady=(10, 16), sticky="ew")

        # Contacts card
        contacts_card = ctk.CTkFrame(left_scroll, fg_color="#101a24", corner_radius=20,
                                      border_width=1, border_color="#173041")
        contacts_card.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        contacts_card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(contacts_card, text="👥  Contacts",
                     font=ctk.CTkFont(size=18, weight="bold")).grid(
            row=0, column=0, padx=18, pady=(16, 8), sticky="w")

        self._em_contacts_list = []
        self._em_count_var = ctk.StringVar(value="No contacts imported yet")
        ctk.CTkLabel(contacts_card, textvariable=self._em_count_var,
                     text_color="#8ea5af").grid(
            row=1, column=0, padx=18, pady=(0, 6), sticky="w")

        self._em_listbox = tk.Listbox(
            contacts_card, height=8, bg="#0c131b", fg="#d8ebf6",
            selectbackground="#173245", font=("Courier New", 9),
            borderwidth=0, highlightthickness=0)
        self._em_listbox.grid(row=3, column=0, padx=18, pady=(0, 16), sticky="ew")

        def import_contacts():
            path = filedialog.askopenfilename(
                title="Import Contacts",
                filetypes=[
                    ("All supported", "*.csv *.xls *.xlsx *.html *.htm"),
                    ("CSV files", "*.csv"),
                    ("Excel files", "*.xls *.xlsx"),
                    ("HTML files", "*.html *.htm"),
                ])
            if not path:
                return
            try:
                import sys as _sys
                _sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
                from modules.data_importer import UniversalDataImporter
                result = UniversalDataImporter().import_file(path)
                self._em_contacts_list = result.contacts
                self._em_count_var.set(
                    f"✅  {result.total} contacts  •  {result.skipped} skipped")
                self._em_listbox.delete(0, "end")
                for c in result.contacts:
                    self._em_listbox.insert(
                        "end",
                        f"{c.get('name','?'):<20}  {c.get('email','(no email)')}")
                if result.errors:
                    messagebox.showwarning("Import Warnings",
                                           "\n".join(result.errors[:5]))
            except Exception as ex:
                messagebox.showerror("Import Error", str(ex))

        ctk.CTkButton(contacts_card, text="📂  Import CSV / Excel / HTML",
                      command=import_contacts).grid(
            row=2, column=0, padx=18, pady=(0, 6), sticky="ew")

        # ── RIGHT panel ───────────────────────────────────────────────────────────
        right = ctk.CTkFrame(frame, fg_color="#0a1118", corner_radius=0)
        right.grid(row=1, column=1, sticky="nsew")
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(1, weight=1)

        # Template + Subject
        compose_hdr = ctk.CTkFrame(right, fg_color="#101a24", corner_radius=20,
                                    border_width=1, border_color="#173041")
        compose_hdr.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        compose_hdr.grid_columnconfigure(1, weight=1)

        self._em_tpl_var  = ctk.StringVar(value="(none)")
        self._em_subj_var = ctk.StringVar(value="Hello {name}!")

        def on_template(val):
            subj, html = EMAIL_TEMPLATES.get(val, ("", ""))
            if subj:
                self._em_subj_var.set(subj)
            if html:
                self._em_body.delete("1.0", "end")
                self._em_body.insert("1.0", html)

        ctk.CTkLabel(compose_hdr, text="Template").grid(
            row=0, column=0, padx=18, pady=10, sticky="w")
        ctk.CTkOptionMenu(compose_hdr, values=list(EMAIL_TEMPLATES.keys()),
                          variable=self._em_tpl_var, command=on_template,
                          fg_color="#173245", button_color="#1d3545",
                          button_hover_color="#203243", text_color="#d8ebf6",
                          dropdown_fg_color="#101a24",
                          dropdown_hover_color="#203243",
                          dropdown_text_color="#dbe8f0").grid(
            row=0, column=1, padx=(4, 18), pady=10, sticky="ew")

        ctk.CTkLabel(compose_hdr, text="Subject").grid(
            row=1, column=0, padx=18, pady=(0, 10), sticky="w")
        ctk.CTkEntry(compose_hdr, textvariable=self._em_subj_var,
                     fg_color="#0c131b", border_color="#173041").grid(
            row=1, column=1, padx=(4, 18), pady=(0, 10), sticky="ew")

        # Variable chips
        chips = ctk.CTkFrame(compose_hdr, fg_color="transparent")
        chips.grid(row=2, column=0, columnspan=2, padx=14, pady=(0, 12), sticky="w")
        ctk.CTkLabel(chips, text="Variables:", text_color="#8ea5af").grid(
            row=0, column=0, padx=(0, 8))
        for i, v in enumerate(["{name}", "{email}", "{amount}", "{date}", "{invoice_no}"]):
            ctk.CTkLabel(chips, text=v, fg_color="#1d3545", corner_radius=999,
                         padx=10, pady=4, text_color="#d8ebf6").grid(
                row=0, column=i + 1, padx=4)

        # HTML Body editor
        body_card = ctk.CTkFrame(right, fg_color="#101a24", corner_radius=20,
                                  border_width=1, border_color="#173041")
        body_card.grid(row=1, column=0, sticky="nsew", pady=(0, 8))
        body_card.grid_columnconfigure(0, weight=1)
        body_card.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(body_card,
                     text="📝  HTML Body  —  use {name} {email} {amount} {date} etc.",
                     font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=0, column=0, padx=18, pady=(14, 6), sticky="w")

        self._em_body = tk.Text(
            body_card, wrap="word",
            bg="#0c131b", fg="#d8ebf6",
            insertbackground="#d8ebf6",
            font=("Courier New", 10),
            borderwidth=0, highlightthickness=0, relief="flat")
        self._em_body.insert("1.0",
            "<p>Dear <strong>{name}</strong>,</p>\n<p>Your message here.</p>")
        self._em_body.grid(row=1, column=0, padx=18, pady=(0, 18), sticky="nsew")

        # Progress + Controls
        ctrl = ctk.CTkFrame(right, fg_color="#101a24", corner_radius=20,
                             border_width=1, border_color="#173041")
        ctrl.grid(row=2, column=0, sticky="ew")
        ctrl.grid_columnconfigure(2, weight=1)

        self._em_bar = ctk.CTkProgressBar(ctrl, progress_color="#39b37a")
        self._em_bar.grid(row=0, column=0, columnspan=4,
                           padx=18, pady=(14, 6), sticky="ew")
        self._em_bar.set(0)

        self._em_status = ctk.StringVar(value="Ready.")
        ctk.CTkLabel(ctrl, textvariable=self._em_status,
                     text_color="#8ea5af").grid(
            row=1, column=0, columnspan=4, padx=18, pady=(0, 6), sticky="w")

        self._em_log_widget = tk.Text(
            ctrl, height=5, bg="#0c131b", fg="#9db1bd",
            font=("Courier New", 9), state="disabled",
            borderwidth=0, highlightthickness=0)
        self._em_log_widget.grid(row=2, column=0, columnspan=4,
                                  padx=18, pady=(0, 8), sticky="ew")

        def _log(msg):
            self._em_log_widget.configure(state="normal")
            self._em_log_widget.insert("end", msg + "\n")
            self._em_log_widget.see("end")
            self._em_log_widget.configure(state="disabled")

        self._em_stop_flag = threading.Event()

        def start_campaign():
            contacts = [c for c in self._em_contacts_list if c.get("email")]
            if not contacts:
                messagebox.showwarning("No Contacts",
                    "Import contacts with email addresses first.")
                return
            if not self._em_user.get() or not self._em_pass.get():
                messagebox.showwarning("Missing SMTP",
                    "Enter your SMTP username and password.")
                return
            if not messagebox.askyesno("Confirm Send",
                f"Send to {len(contacts)} contacts?\n\n"
                "Make sure you have their consent (legal requirement)."):
                return

            self._em_stop_flag.clear()
            self._em_bar.set(0)
            btn_start.configure(state="disabled")
            btn_stop.configure(state="normal")

            def worker():
                try:
                    ctx = ssl.create_default_context()
                    conn = smtplib.SMTP(
                        self._em_host.get(), int(self._em_port.get()))
                    conn.starttls(context=ctx)
                    conn.login(self._em_user.get(), self._em_pass.get())
                except Exception as ex:
                    self.after(0, lambda: (
                        messagebox.showerror("SMTP Error", str(ex)),
                        btn_start.configure(state="normal"),
                        btn_stop.configure(state="disabled"),
                    ))
                    return

                sent = 0
                total = len(contacts)
                for i, contact in enumerate(contacts):
                    if self._em_stop_flag.is_set():
                        break

                    to_addr = contact.get("email", "").strip()
                    if not to_addr:
                        continue

                    vars_map = dict(contact)
                    # strip custom_ prefix for template use
                    for k in list(vars_map.keys()):
                        if k.startswith("custom_"):
                            vars_map[k[7:]] = vars_map.pop(k)
                    vars_map.setdefault("sender", self._em_from_name.get())

                    def substitute(text):
                        for k, v in vars_map.items():
                            text = text.replace(f"{{{k}}}", str(v))
                        return text

                    try:
                        msg = MIMEMultipart("alternative")
                        msg["Subject"] = substitute(self._em_subj_var.get())
                        msg["From"] = (
                            f"{self._em_from_name.get()} "
                            f"<{self._em_from_addr.get()}>")
                        msg["To"] = to_addr
                        html_body = substitute(
                            self._em_body.get("1.0", "end"))
                        msg.attach(MIMEText(html_body, "html", "utf-8"))
                        conn.sendmail(self._em_from_addr.get(),
                                      to_addr, msg.as_string())
                        sent += 1
                        progress = sent / total

                        def _update(e=to_addr, s=sent, p=progress):
                            _log(f"✅ Sent → {e}")
                            self._em_status.set(
                                f"Sent: {s} / {total}")
                            self._em_bar.set(p)

                        self.after(0, _update)

                    except Exception as ex:
                        def _fail(e=to_addr, er=str(ex)):
                            _log(f"❌ Failed {e}: {er}")
                        self.after(0, _fail)

                    import time
                    time.sleep(float(self._em_delay.get() or 5))

                try:
                    conn.quit()
                except Exception:
                    pass

                def finish():
                    btn_start.configure(state="normal")
                    btn_stop.configure(state="disabled")
                    self._em_bar.set(1)
                    failed = total - sent
                    self._em_status.set(
                        f"Done! ✅ Sent: {sent}  ❌ Failed: {failed}")
                    messagebox.showinfo(
                        "Campaign Complete",
                        f"Sent: {sent}\nFailed: {failed}")

                self.after(0, finish)

            threading.Thread(target=worker, daemon=True).start()

        def stop_campaign():
            self._em_stop_flag.set()
            self._em_status.set("Stopping…")

        btn_start = ctk.CTkButton(
            ctrl, text="🚀  Start Email Campaign",
            fg_color="#1c6b4d", hover_color="#24895f",
            command=start_campaign)
        btn_start.grid(row=3, column=0, padx=(18, 8), pady=(0, 14))

        btn_stop = ctk.CTkButton(
            ctrl, text="⏹  Stop",
            fg_color="#7d3037", hover_color="#a23e46",
            state="disabled", command=stop_campaign)
        btn_stop.grid(row=3, column=1, padx=(0, 18), pady=(0, 14))

    def _on_close(self) -> None:
        try:
            self.whatsapp_sender.shutdown()
        finally:
            self.destroy()
