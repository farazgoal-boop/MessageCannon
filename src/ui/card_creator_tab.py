"""
MessageCannon Pro — Card Creator V2
Complete in-app card builder with live HTML preview, section management,
bulk send via WhatsApp + Email, and read/unread tracking.
"""

import logging
import html as html_module
import tkinter as tk
from tkinter import filedialog, messagebox, colorchooser
import customtkinter as ctk
import threading
import webbrowser
import re
import json
import tempfile
import time
from pathlib import Path
from datetime import datetime, date
from typing import Dict, List

from ..core import ai_service
from ..core.ai_service import AIServiceError
from ..models import Contact
from ..modules.data_importer import UniversalDataImporter
from ..utils.validators import DataValidator, PhoneValidator
from . import theme as T
from .toast import show_toast

logger = logging.getLogger(__name__)

try:
    from tkinterweb import HtmlFrame
    HAS_HTML_PREVIEW = True
except ImportError:
    HAS_HTML_PREVIEW = False
    logger.warning("tkinterweb not installed — card preview falls back to browser only")


# ── Section types available in card builder ───────────────────────────────────
SECTION_TYPES = [
    ("🖼️ Banner Image",    "banner"),
    ("▶️ YouTube Video",   "youtube"),
    ("📝 Text Block",      "text"),
    ("✅ Features List",   "features"),
    ("💰 Price Box",       "price"),
    ("🔗 Links Row",       "links"),
    ("📞 Contact Footer",  "contact"),
]

APP_PRESETS = {
    "MessageCannon Pro": {
        "icon": "📨", "tagline": "Bulk Messaging Tool", "accent": "#6c63ff",
        "description": "Pakistan's most advanced bulk messaging platform.",
        "features": "✅ WhatsApp bulk messaging\n✅ HTML email campaigns\n✅ CSV/Excel/HTML import\n✅ Variable substitution\n✅ Campaign analytics",
        "price": "$89", "old_price": "$129", "price_note": "One-time · Lifetime",
    },
    "Copilot Premium": {
        "icon": "🤖", "tagline": "AI Productivity", "accent": "#0078d4",
        "description": "Your AI-powered productivity assistant.",
        "features": "✅ AI content generation\n✅ Smart automation\n✅ Multi-language\n✅ Cloud sync",
        "price": "$49", "old_price": "$99", "price_note": "Annual subscription",
    },
    "JobMind Match": {
        "icon": "💼", "tagline": "Job Matching AI", "accent": "#00b894",
        "description": "AI-driven job matching platform.",
        "features": "✅ AI resume analysis\n✅ Smart job matching\n✅ Interview scheduler",
        "price": "$29/mo", "old_price": "$59/mo", "price_note": "Cancel anytime",
    },
    "Shaz Residency": {
        "icon": "🏢", "tagline": "Real Estate", "accent": "#e17055",
        "description": "Premium real estate platform across Pakistan.",
        "features": "✅ Verified listings\n✅ 3D virtual tours\n✅ Price analytics",
        "price": "Free", "old_price": "", "price_note": "Premium listings available",
    },
    "Custom": {
        "icon": "⭐", "tagline": "", "accent": "#6c63ff",
        "description": "", "features": "", "price": "", "old_price": "", "price_note": "",
    },
}

ACCENT_COLORS = [
    "#4f46e5",  # indigo
    "#0891b2",  # cyan
    "#0d9488",  # teal
    "#7c3aed",  # violet
    "#e11d48",  # rose
]

CARD_STYLE_TEMPLATES = {
    "Dark Premium": {
        "bg": "#1a1a2e", "body_bg": "#111827", "text": "rgba(255,255,255,0.85)",
        "accent": "#6c63ff", "header_bg": "#0a1628",
    },
    "Light Minimal": {
        "bg": "#ffffff", "body_bg": "#f5f7fa", "text": "#333333",
        "accent": "#2563eb", "header_bg": "#ffffff",
    },
    "Gradient Bold": {
        "bg": "#1a1a2e", "body_bg": "linear-gradient(135deg,#667eea,#764ba2)",
        "text": "#ffffff", "accent": "#f39c12", "header_bg": "#667eea",
    },
    "Corporate Blue": {
        "bg": "#ffffff", "body_bg": "#eef2f7", "text": "#1e3a5f",
        "accent": "#1e3a5f", "header_bg": "#1e3a5f",
    },
    "Green Tech": {
        "bg": "#0d1f17", "body_bg": "#122820", "text": "#d1fae5",
        "accent": "#10b981", "header_bg": "#064e3b",
    },
    "Red Urgent": {
        "bg": "#1a0a0a", "body_bg": "#2d1212", "text": "#fecaca",
        "accent": "#ef4444", "header_bg": "#7f1d1d",
    },
}


def get_yt_id(url: str) -> str:
    m = re.search(r"(?:v=|youtu\.be/|embed/)([a-zA-Z0-9_-]{11})", url)
    return m.group(1) if m else ""


def get_yt_thumbnail(vid_id: str) -> str:
    """YouTube HQ thumbnail URL for in-app preview."""
    return f"https://img.youtube.com/vi/{vid_id}/hqdefault.jpg"


def safe_attr(value: str) -> str:
    """Escape a string for safe use inside an HTML attribute."""
    return html_module.escape(str(value), quote=True)


def safe_text(value: str) -> str:
    """Escape a string for safe use as HTML text content."""
    return html_module.escape(str(value), quote=False)


def _clean_url(url: str) -> str:
    """Strip whitespace and stray surrounding quotes from pasted URLs."""
    return str(url).strip().strip('"').strip("'").strip()


def _contact_key(contact: Contact) -> str:
    """Stable per-contact identifier used to line up AI-personalized messages."""
    return (contact.phone or contact.email or "").strip()


def _rows_to_contacts(rows: List[dict]) -> List[Contact]:
    """Convert UniversalDataImporter's flat custom_-prefixed dicts into real
    Contact objects — mirrors core/contact_manager.py:import_from_file()."""
    phone_validator = PhoneValidator()
    contacts: List[Contact] = []
    for row in rows:
        phone_raw = row.get("phone", "")
        email_raw = row.get("email", "")
        name = row.get("name", "")

        normalized_phone = ""
        if phone_raw:
            normalized_phone, _phone_error = phone_validator.normalize_phone(phone_raw)
            if normalized_phone is None and not email_raw:
                continue
            normalized_phone = normalized_phone or ""

        if email_raw and not DataValidator.is_valid_email(email_raw):
            if not normalized_phone:
                continue
            email_raw = ""

        if not normalized_phone and not email_raw:
            continue

        custom_fields = {
            key[7:]: value
            for key, value in row.items()
            if key.startswith("custom_") and value
        }

        contacts.append(Contact(
            phone=normalized_phone or "",
            email=email_raw or "",
            name=name or "",
            custom_fields=custom_fields or {},
        ))
    return contacts


def generate_html(sections: list, meta: dict, for_preview: bool = False) -> str:
    """Generate complete standalone HTML card from sections + meta."""
    accent   = meta.get("accent", "#6c63ff")
    app_name = safe_text(meta.get("app_name", "My App"))
    icon     = meta.get("icon", "⭐")
    tagline  = safe_text(meta.get("tagline", ""))
    org      = safe_text(meta.get("org", "Faraz Automation"))
    wa       = safe_text(meta.get("wa", "+92 316 2400657"))
    email    = safe_text(meta.get("email", "farazgoal@gmail.com"))
    addr     = safe_text(meta.get("addr", "Karachi, Pakistan"))
    style    = meta.get("style", CARD_STYLE_TEMPLATES["Dark Premium"])
    card_bg  = style.get("bg", "#1a1a2e")
    body_bg  = style.get("body_bg", "#111827")
    text_col = style.get("text", "rgba(255,255,255,0.85)")
    header_bg = style.get("header_bg", "#0a1628")
    if not meta.get("accent"):
        accent = style.get("accent", accent)
    buy_url = safe_attr(_clean_url(meta.get("buy_link", "").strip() or "#"))

    body_parts = []

    # Always start with branded header
    body_parts.append(f"""
    <div style="background:{header_bg};padding:20px 24px 0">
      <div style="height:3px;background:linear-gradient(90deg,{accent},{accent}88,{accent});
        margin:-20px -24px 20px;border-radius:20px 20px 0 0"></div>
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:16px">
        <div style="display:flex;align-items:center;gap:12px">
          <div style="width:44px;height:44px;background:{accent};border-radius:12px;
            display:flex;align-items:center;justify-content:center;font-size:22px">{icon}</div>
          <div>
            <div style="font-size:17px;font-weight:500;color:#fff">{app_name}</div>
            <div style="font-size:10px;color:rgba(255,255,255,0.4)">{org}</div>
          </div>
        </div>
        <div style="font-size:10px;padding:4px 12px;border-radius:20px;
          background:rgba(255,255,255,0.08);color:rgba(255,255,255,0.6)">{tagline}</div>
      </div>
    </div>""")

    for sec in sections:
        stype = sec.get("type", "")
        data  = sec.get("data", {})

        if stype == "banner" and data.get("url"):
            banner_url = safe_attr(_clean_url(data["url"]))
            body_parts.append(f"""
    <div style="width:100%;aspect-ratio:16/9;overflow:hidden;background:#111">
      <img src="{banner_url}" style="width:100%;height:100%;object-fit:cover;display:block"
        onerror="this.parentElement.style.background='#1a1a2e'">
    </div>""")

        elif stype == "youtube" and data.get("url"):
            vid = get_yt_id(_clean_url(data["url"]))
            if vid:
                vid_safe = safe_attr(vid)
                if for_preview:
                    thumb = safe_attr(get_yt_thumbnail(vid))
                    body_parts.append(f"""
    <div style="width:100%;aspect-ratio:16/9;background:#000;
      margin-bottom:16px;position:relative;cursor:pointer"
      onclick="window.open('https://youtube.com/watch?v={vid_safe}','_blank')">
      <img src="{thumb}" style="width:100%;height:100%;object-fit:cover;display:block">
      <div style="position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);
        width:60px;height:60px;background:rgba(255,0,0,0.85);border-radius:50%;
        display:flex;align-items:center;justify-content:center">
        <div style="width:0;height:0;border-top:12px solid transparent;
          border-bottom:12px solid transparent;border-left:20px solid white;
          margin-left:4px"></div>
      </div>
    </div>""")
                else:
                    body_parts.append(f"""
    <div style="width:100%;aspect-ratio:16/9;background:#000;margin-bottom:16px">
      <iframe
        width="100%" height="100%"
        src="https://www.youtube.com/embed/{vid_safe}?rel=0&modestbranding=1"
        frameborder="0"
        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
        allowfullscreen
        style="display:block;border:none">
      </iframe>
    </div>""")

        elif stype == "text":
            size    = data.get("size", "medium")
            align   = data.get("align", "left")
            content = safe_text(data.get("content", ""))
            fs = {"small":"12px","medium":"14px","large":"18px","heading":"22px"}.get(size,"14px")
            fw = "500" if size == "heading" else "400"
            body_parts.append(f"""
    <div style="padding:16px 24px">
      <div style="font-size:{fs};font-weight:{fw};color:{text_col};
        line-height:1.65;text-align:{align}">{content}</div>
    </div>""")

        elif stype == "features":
            items = [safe_text(f.strip()) for f in data.get("items","").split("\n") if f.strip()]
            if items:
                rows = "".join(
                    f'<div style="display:flex;align-items:flex-start;gap:8px;margin-bottom:7px">'
                    f'<span style="font-size:13px;color:rgba(255,255,255,0.8);line-height:1.5">{f}</span>'
                    f'</div>' for f in items)
                body_parts.append(f"""
    <div style="padding:12px 24px">{rows}</div>""")

        elif stype == "price":
            price     = safe_text(data.get("price",""))
            old_price = safe_text(data.get("old_price",""))
            note      = safe_text(data.get("note",""))
            if price:
                old_html = f'<span style="font-size:12px;text-decoration:line-through;color:rgba(255,255,255,0.35);margin-left:8px">{old_price}</span>' if old_price else ""
                note_html = f'<div style="font-size:11px;color:rgba(255,255,255,0.45);margin-top:3px">{note}</div>' if note else ""
                buy_btn = (
                    f'<a href="{buy_url}" target="_blank" '
                    f'style="background:{accent};color:#fff;font-size:12px;font-weight:500;'
                    f'padding:9px 20px;border-radius:20px;cursor:pointer;text-decoration:none;'
                    f'display:inline-block">BUY NOW →</a>'
                )
                body_parts.append(f"""
    <div style="margin:8px 24px;background:rgba(255,255,255,0.06);
      border:0.5px solid rgba(255,255,255,0.1);border-radius:12px;
      padding:14px 18px;display:flex;align-items:center;justify-content:space-between">
      <div>
        <div style="display:flex;align-items:baseline">
          <span style="font-size:28px;font-weight:500;color:{accent}">{price}</span>
          {old_html}
        </div>
        {note_html}
      </div>
      {buy_btn}
    </div>""")

        elif stype == "links":
            link_list = data.get("links", [])
            if link_list:
                rows = ""
                icons = {"buy":"🛒","youtube":"▶️","linkedin":"💼","github":"🐙","website":"🌐","gumroad":"🎯","other":"🔗"}
                for lnk in link_list:
                    url = _clean_url(lnk.get("url", ""))
                    if url:
                        ic = icons.get(lnk.get("kind","other"),"🔗")
                        label = safe_text(lnk.get("label", "Link"))
                        url_attr = safe_attr(url)
                        rows += (
                            f'<a href="{url_attr}" target="_blank" '
                            f'style="display:flex;align-items:center;gap:10px;padding:9px 14px;'
                            f'background:rgba(255,255,255,0.05);border-radius:8px;'
                            f'text-decoration:none;margin-bottom:6px;'
                            f'border:0.5px solid rgba(255,255,255,0.08)">'
                            f'<span style="font-size:15px">{ic}</span>'
                            f'<span style="font-size:12px;color:rgba(255,255,255,0.75);flex:1">{label}</span>'
                            f'<span style="font-size:11px;color:rgba(255,255,255,0.3)">↗</span></a>'
                        )
                body_parts.append(f'<div style="padding:8px 24px">{rows}</div>')

        elif stype == "contact":
            body_parts.append(f"""
    <div style="height:0.5px;background:rgba(255,255,255,0.08);margin:4px 24px"></div>
    <div style="padding:14px 24px 20px;display:flex;align-items:flex-end;justify-content:space-between">
      <div>
        <div style="font-size:12px;font-weight:500;color:{accent};margin-bottom:6px">{org}</div>
        <div style="font-size:11px;color:rgba(255,255,255,0.5);margin-bottom:3px">📱 {wa}</div>
        <div style="font-size:11px;color:rgba(255,255,255,0.5);margin-bottom:3px">✉️ {email}</div>
        <div style="font-size:11px;color:rgba(255,255,255,0.4)">📍 {addr}</div>
      </div>
      <div style="text-align:right">
        <div style="width:40px;height:40px;background:{accent}22;border:0.5px solid {accent}55;
          border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:20px">⊞</div>
        <div style="font-size:9px;color:rgba(255,255,255,0.2);margin-top:3px">QR Code</div>
      </div>
    </div>""")

    body_html = "\n".join(body_parts)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{app_name} — {org}</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{background:{body_bg};font-family:Arial,Helvetica,sans-serif;
    min-height:100vh;display:flex;align-items:flex-start;
    justify-content:center;padding:20px}}
  .card{{width:100%;max-width:520px;background:{card_bg};
    border-radius:20px;overflow:hidden;
    border:0.5px solid rgba(255,255,255,0.08);
    box-shadow:0 20px 60px rgba(0,0,0,0.5)}}
  .footer-tag{{text-align:center;margin-top:10px;font-size:10px;
    color:rgba(255,255,255,0.2)}}
</style>
</head>
<body>
<div>
  <div class="card">
{body_html}
  </div>
  <div class="footer-tag">Created with MessageCannon Pro · {org}</div>
</div>
</body>
</html>"""


class CardCreatorV2(ctk.CTkFrame):
    """
    Card Creator V2 — complete in-app card builder.
    Sections: Banner, YouTube, Text, Features, Price, Links, Contact
    Actions: Preview in browser, Save HTML, Bulk send WA, Bulk send Email
    """

    def __init__(self, parent, main_window=None, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self.main_window = main_window
        self._accent   = "#6c63ff"
        self._sections = []   # list of {"type":str, "data":dict, "frame":widget}
        self._html     = ""
        self._bulk_contacts: List[Contact] = []   # set by bulk-send dialog's import step
        self._bulk_messages: Dict[str, str] = {}  # contact key -> AI-personalized message
        self._preview_job = None
        self._style_name = "Dark Premium"
        self._buy_var = ctk.StringVar(value="")
        self._meta     = {
            "app_name": "MessageCannon Pro",
            "icon":     "📨",
            "tagline":  "Bulk Messaging Tool",
            "accent":   "#6c63ff",
            "org":      "Faraz Automation",
            "wa":       "+92 316 2400657",
            "email":    "farazgoal@gmail.com",
            "addr":     "Karachi, Pakistan",
        }
        self._build_ui()
        # Load default sections
        self._load_preset("MessageCannon Pro")
        self.after(800, self._schedule_preview)

    # ─── Main layout ──────────────────────────────────────────────────────────

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Outer paned: left editor | right preview+actions
        paned = ctk.CTkFrame(self, fg_color="transparent")
        paned.grid(row=0, column=0, sticky="nsew")
        paned.grid_columnconfigure(0, weight=3)
        paned.grid_columnconfigure(1, weight=2)
        paned.grid_rowconfigure(0, weight=1)

        self._build_editor(paned)
        self._build_preview_panel(paned)

    # ─── LEFT: editor ─────────────────────────────────────────────────────────

    def _build_editor(self, parent):
        left = ctk.CTkFrame(parent, fg_color="transparent")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        left.grid_columnconfigure(0, weight=1)
        left.grid_rowconfigure(1, weight=1)

        # ── Top: app selector + meta ──────────────────────────────────────────
        top = ctk.CTkFrame(left, fg_color=T.BG_SURFACE, corner_radius=14,
                            border_width=1, border_color=T.BG_BORDER)
        top.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        top.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(top, text="🎯  Card Identity",
                     font=ctk.CTkFont(size=14, weight="bold"),
                     text_color=T.TEXT_HEAD).grid(
            row=0, column=0, padx=16, pady=(14, 8), sticky="w")

        # ── AI card generation — promoted to the primary, easiest path ─────────
        ai_row = ctk.CTkFrame(top, fg_color=T.BG_INNER, corner_radius=12,
                               border_width=2, border_color=T.ACCENT)
        ai_row.grid(row=1, column=0, padx=16, pady=(0, 14), sticky="ew")
        ai_row.grid_columnconfigure(0, weight=1)

        ai_header = ctk.CTkFrame(ai_row, fg_color="transparent")
        ai_header.grid(row=0, column=0, padx=12, pady=(12, 4), sticky="w")
        ctk.CTkLabel(ai_header, text="✨ AI-POWERED", fg_color=T.BADGE_BG,
                     corner_radius=999, text_color=T.ACCENT,
                     font=ctk.CTkFont(size=10, weight="bold"),
                     padx=10, pady=3).pack(side="left")
        ctk.CTkLabel(ai_header, text="  Describe your product — AI drafts the whole card",
                     text_color=T.TEXT_HEAD, font=ctk.CTkFont(size=12, weight="bold")).pack(
            side="left", padx=(8, 0))

        self._ai_desc_box = ctk.CTkTextbox(
            ai_row, height=54, fg_color=T.BG_MAIN, text_color=T.TEXT_HEAD,
            border_color=T.BG_BORDER, border_width=1, font=ctk.CTkFont(size=11))
        self._ai_desc_box.grid(row=1, column=0, padx=12, pady=(0, 8), sticky="ew")
        ai_btn_row = ctk.CTkFrame(ai_row, fg_color="transparent")
        ai_btn_row.grid(row=2, column=0, padx=12, pady=(0, 12), sticky="ew")
        self._ai_generate_btn = ctk.CTkButton(
            ai_btn_row, text="✨ Generate with AI", fg_color=T.ACCENT, hover_color=T.ACCENT_HOVER,
            text_color=T.TEXT_HEAD, font=ctk.CTkFont(size=12, weight="bold"),
            height=34, command=self._generate_card_with_ai)
        self._ai_generate_btn.pack(side="left")
        self._ai_status_var = ctk.StringVar(value="")
        ctk.CTkLabel(ai_btn_row, textvariable=self._ai_status_var,
                     text_color=T.TEXT_MUTED, font=ctk.CTkFont(size=11)).pack(
            side="left", padx=(10, 0))

        ctk.CTkLabel(top, text="OR START FROM A TEMPLATE",
                     text_color=T.TEXT_DIM, font=ctk.CTkFont(size=10, weight="bold")).grid(
            row=2, column=0, padx=16, pady=(0, 4), sticky="w")

        # App buttons — segmented preset picker
        bf = ctk.CTkFrame(top, fg_color="transparent")
        bf.grid(row=3, column=0, padx=16, pady=(0, 8), sticky="ew")
        self._app_btns = {}
        for i, (name, _) in enumerate(APP_PRESETS.items()):
            b = ctk.CTkButton(bf, text=name, width=1,
                              font=ctk.CTkFont(size=11),
                              fg_color=T.BADGE_BG, hover_color=T.BG_BORDER,
                              text_color=T.TEXT_HEAD,
                              command=lambda n=name: self._load_preset(n))
            b.grid(row=i//3, column=i%3, padx=3, pady=3, sticky="ew")
            bf.grid_columnconfigure(i%3, weight=1)
            self._app_btns[name] = b

        # Meta fields row
        mf = ctk.CTkFrame(top, fg_color="transparent")
        mf.grid(row=4, column=0, padx=16, pady=(0, 8), sticky="ew")
        mf.grid_columnconfigure((0,1,2,3), weight=1)

        self._mname = ctk.StringVar(value="MessageCannon Pro")
        self._micon = ctk.StringVar(value="📨")
        self._mtag  = ctk.StringVar(value="Bulk Messaging Tool")

        for i,(lbl,var,ph) in enumerate([
            ("App Name", self._mname, "My App"),
            ("Icon",     self._micon, "⭐"),
            ("Tagline",  self._mtag,  "Short tagline"),
        ]):
            ctk.CTkLabel(mf, text=lbl, text_color=T.TEXT_MUTED,
                         font=ctk.CTkFont(size=11)).grid(row=0,column=i,sticky="w",padx=2)
            ctk.CTkEntry(mf, textvariable=var, placeholder_text=ph,
                         fg_color=T.BG_INNER, border_color=T.BG_BORDER,
                         text_color=T.TEXT_HEAD,
                         placeholder_text_color=T.TEXT_DIM,
                         font=ctk.CTkFont(size=11)).grid(
                row=1,column=i,sticky="ew",padx=2)
            var.trace_add("write", lambda *_: self._schedule_preview())

        # Accent colors
        cf = ctk.CTkFrame(top, fg_color="transparent")
        cf.grid(row=5, column=0, padx=16, pady=(0,12), sticky="w")
        ctk.CTkLabel(cf, text="Theme:", text_color=T.TEXT_MUTED,
                     font=ctk.CTkFont(size=11)).grid(row=0,column=0,padx=(0,6))
        for i,c in enumerate(ACCENT_COLORS):
            b = tk.Button(cf, bg=c, relief="flat", width=2, height=1,
                          cursor="hand2", command=lambda h=c: self._set_accent(h))
            b.grid(row=0, column=i+1, padx=2)
        ctk.CTkButton(cf, text="Custom", width=60,
                      fg_color=T.BADGE_BG, hover_color=T.BG_BORDER,
                      font=ctk.CTkFont(size=11),
                      command=self._custom_color).grid(row=0,column=len(ACCENT_COLORS)+1,padx=(6,0))

        tf = ctk.CTkFrame(top, fg_color="transparent")
        tf.grid(row=6, column=0, padx=16, pady=(0, 14), sticky="ew")
        ctk.CTkLabel(tf, text="Card Template:", text_color=T.TEXT_MUTED,
                     font=ctk.CTkFont(size=11)).grid(row=0, column=0, padx=(0, 8))
        self._template_var = ctk.StringVar(value="Dark Premium")
        ctk.CTkOptionMenu(
            tf, values=list(CARD_STYLE_TEMPLATES.keys()),
            variable=self._template_var, command=self._apply_card_template,
            fg_color=T.BADGE_BG, button_color=T.BADGE_BG,
            button_hover_color=T.BG_BORDER,
            text_color=T.TEXT_HEAD,
            dropdown_fg_color=T.BG_SURFACE,
            dropdown_hover_color=T.BG_BORDER,
            dropdown_text_color=T.TEXT_HEAD,
            width=180, font=ctk.CTkFont(size=11),
        ).grid(row=0, column=1, sticky="w")

        # ── Middle: sections list ─────────────────────────────────────────────
        mid = ctk.CTkFrame(left, fg_color="transparent")
        mid.grid(row=1, column=0, sticky="nsew")
        mid.grid_columnconfigure(0, weight=1)
        mid.grid_rowconfigure(1, weight=1)

        # Add section toolbar
        tb = ctk.CTkFrame(mid, fg_color=T.BG_SURFACE, corner_radius=12,
                           border_width=1, border_color=T.BG_BORDER)
        tb.grid(row=0, column=0, sticky="ew", pady=(0,6))
        ctk.CTkLabel(tb, text="➕  Add Section:",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color=T.TEXT_HEAD).grid(
            row=0,column=0,padx=12,pady=8,sticky="w")
        sbf = ctk.CTkFrame(tb, fg_color="transparent")
        sbf.grid(row=0,column=1,padx=(0,12),pady=6,sticky="e")
        for i,(label,stype) in enumerate(SECTION_TYPES):
            ctk.CTkButton(sbf, text=label, width=1,
                          font=ctk.CTkFont(size=11),
                          fg_color=T.BADGE_BG, hover_color=T.ACCENT_HOVER,
                          text_color=T.TEXT_HEAD,
                          command=lambda t=stype: self._add_section(t)).grid(
                row=i//4, column=i%4, padx=3, pady=3)
            sbf.grid_columnconfigure(i%4, weight=1)

        # Sections scroll area
        self._sections_scroll = ctk.CTkScrollableFrame(
            mid, fg_color=T.BG_MAIN, corner_radius=12)
        self._sections_scroll.grid(row=1,column=0,sticky="nsew")
        self._sections_scroll.grid_columnconfigure(0,weight=1)
        self._sec_row = 0

        # ── Bottom: generate buttons ──────────────────────────────────────────
        bot = ctk.CTkFrame(left, fg_color="transparent")
        bot.grid(row=2, column=0, sticky="ew", pady=(8,0))
        bot.grid_columnconfigure(0, weight=1)

        ctk.CTkButton(bot,
                      text="✨  Generate Card",
                      font=ctk.CTkFont(size=14, weight="bold"),
                      height=42, fg_color=T.ACCENT, hover_color=T.ACCENT_HOVER,
                      command=self._generate).grid(
            row=0, column=0, sticky="ew", pady=(0,6))

        r2 = ctk.CTkFrame(bot, fg_color="transparent")
        r2.grid(row=1, column=0, sticky="ew")
        r2.grid_columnconfigure((0,1,2), weight=1)
        ctk.CTkButton(r2, text="🌐 Open Browser",
                      fg_color=T.SUCCESS, hover_color=T.SUCCESS,
                      text_color=T.TEXT_HEAD,
                      command=self._open_browser).grid(row=0,column=0,padx=(0,4),sticky="ew")
        ctk.CTkButton(r2, text="💾 Save HTML",
                      fg_color=T.BADGE_BG, hover_color=T.BG_BORDER,
                      text_color=T.TEXT_HEAD,
                      command=self._save_html).grid(row=0,column=1,padx=4,sticky="ew")
        ctk.CTkButton(r2, text="📤 Bulk Send",
                      fg_color=T.DANGER, hover_color=T.DANGER_HOVER,
                      text_color=T.TEXT_HEAD,
                      command=self._show_bulk_send).grid(row=0,column=2,padx=(4,0),sticky="ew")

        self._status = ctk.StringVar(value="Add sections and click Generate.")
        ctk.CTkLabel(bot, textvariable=self._status,
                     text_color=T.TEXT_MUTED, font=ctk.CTkFont(size=11)).grid(
            row=2, column=0, pady=(6,0))

    # ─── RIGHT: preview + send stats ──────────────────────────────────────────

    def _build_preview_panel(self, parent):
        right = ctk.CTkFrame(parent, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew")
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(0, weight=2)
        right.grid_rowconfigure(1, weight=1)

        # HTML preview
        prev = ctk.CTkFrame(right, fg_color=T.BG_SURFACE, corner_radius=14,
                             border_width=1, border_color=T.BG_BORDER)
        prev.grid(row=0, column=0, sticky="nsew", pady=(0,8))
        prev.grid_columnconfigure(0, weight=1)
        prev.grid_columnconfigure(1, weight=0)

        ctk.CTkLabel(prev, text="👁  Live Card Preview",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color=T.TEXT_HEAD).grid(
            row=0, column=0, padx=14, pady=(12, 6), sticky="w")

        toolbar = ctk.CTkFrame(prev, fg_color="transparent")
        toolbar.grid(row=0, column=1, padx=14, pady=(12, 6), sticky="e")
        ctk.CTkButton(
            toolbar, text="⛶ Full Screen", width=110, height=28,
            fg_color=T.BADGE_BG, hover_color=T.BG_BORDER,
            text_color=T.TEXT_HEAD,
            font=ctk.CTkFont(size=11),
            command=self._open_browser,
        ).pack(side="left", padx=(0, 6))
        ctk.CTkButton(
            toolbar, text="↻ Refresh", width=80, height=28,
            fg_color=T.BADGE_BG, hover_color=T.BG_BORDER,
            text_color=T.TEXT_HEAD,
            font=ctk.CTkFont(size=11),
            command=self._update_live_preview,
        ).pack(side="left")

        preview_host = tk.Frame(prev, bg=T.resolve(T.BG_INNER), highlightthickness=0)
        preview_host.grid(row=1, column=0, columnspan=2, padx=12, pady=(0, 12), sticky="nsew")

        self._preview_host = preview_host
        self._html_frame = None
        self._preview_fallback = ctk.CTkLabel(
            preview_host,
            text="Card preview loads when you edit sections.\nClick Full Screen to open in browser.",
            text_color=T.TEXT_MUTED,
            font=ctk.CTkFont(size=11),
        )
        self._preview_fallback.pack(fill="both", expand=True, padx=20, pady=40)

        prev.grid_rowconfigure(1, weight=1)

        # Stats / Read-Unread panel
        stats = ctk.CTkFrame(right, fg_color=T.BG_SURFACE, corner_radius=14,
                              border_width=1, border_color=T.BG_BORDER)
        stats.grid(row=1, column=0, sticky="nsew")
        stats.grid_columnconfigure(0, weight=1)
        stats.grid_rowconfigure(1, weight=1)

        sh = ctk.CTkFrame(stats, fg_color="transparent")
        sh.grid(row=0, column=0, padx=14, pady=(12,6), sticky="ew")
        sh.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(sh, text="📊  Send Summary",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color=T.TEXT_HEAD).grid(
            row=0, column=0, sticky="w")
        ctk.CTkButton(sh, text="Refresh", width=70,
                      fg_color=T.BADGE_BG, hover_color=T.BG_BORDER,
                      text_color=T.TEXT_HEAD,
                      font=ctk.CTkFont(size=11),
                      command=self._refresh_stats).grid(row=0, column=1)

        # Stats counters
        cnt = ctk.CTkFrame(stats, fg_color="transparent")
        cnt.grid(row=1, column=0, padx=14, pady=(0,8), sticky="ew")
        cnt.grid_columnconfigure((0,1,2,3), weight=1)

        self._stat_vars = {}
        for i,(lbl,key) in enumerate([
            ("Total",  "total"),
            ("Sent",   "sent"),
            ("Read",   "read"),
            ("Unread", "unread"),
        ]):
            f = ctk.CTkFrame(cnt, fg_color=T.BADGE_BG, corner_radius=10)
            f.grid(row=0, column=i, padx=4, pady=4, sticky="ew")
            v = ctk.StringVar(value="0")
            self._stat_vars[key] = v
            ctk.CTkLabel(f, text=lbl, text_color=T.TEXT_HEAD,
                         font=ctk.CTkFont(size=9)).pack(anchor="w",padx=8,pady=(8,2))
            ctk.CTkLabel(f, textvariable=v,
                         font=ctk.CTkFont(size=18,weight="bold"),
                         text_color=T.ACCENT).pack(anchor="w",padx=8,pady=(0,8))

        # Daily summary list
        ctk.CTkLabel(stats, text="📅  Today's Activity (Read / Unread)",
                     text_color=T.TEXT_MUTED,
                     font=ctk.CTkFont(size=11)).grid(
            row=2, column=0, padx=14, pady=(0,4), sticky="w")

        self._log_box = ctk.CTkTextbox(
            stats, height=120, fg_color=T.BG_INNER,
            text_color=T.TEXT_HEAD,
            font=ctk.CTkFont(family="Courier New", size=9),
            state="disabled")
        self._log_box.grid(row=3, column=0, padx=12, pady=(0,12), sticky="ew")

        self._send_log = []   # {"time":str,"to":str,"channel":str,"status":str}
        self._refresh_stats()

    # ─── Section management ───────────────────────────────────────────────────

    def _add_section(self, stype: str):
        idx = len(self._sections)
        data: dict = {}
        visible_var = ctk.BooleanVar(value=True)

        card = ctk.CTkFrame(self._sections_scroll, fg_color=T.BG_SURFACE,
                             corner_radius=12, border_width=1, border_color=T.BG_BORDER)
        card.grid(row=self._sec_row, column=0, sticky="ew", pady=(0, 6), padx=2)
        card.grid_columnconfigure(0, weight=1)
        self._sec_row += 1

        label = next((lbl for lbl, t in SECTION_TYPES if t == stype), stype)
        section_num = idx + 1

        hdr = ctk.CTkFrame(card, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 4))
        hdr.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(hdr, text="↕", text_color=T.ACCENT,
                     font=ctk.CTkFont(size=14)).grid(row=0, column=0, padx=(0, 8))
        title_lbl = ctk.CTkLabel(
            hdr,
            text=f"Section {section_num}: {label}",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=T.TEXT_HEAD,
        )
        title_lbl.grid(row=0, column=1, sticky="w")

        ctrl = ctk.CTkFrame(hdr, fg_color="transparent")
        ctrl.grid(row=0, column=2, sticky="e")

        def toggle_visible():
            if visible_var.get():
                body.grid()
            else:
                body.grid_remove()
            self._schedule_preview()

        ctk.CTkCheckBox(
            ctrl, text="Show", variable=visible_var, width=70,
            command=toggle_visible,
            text_color=T.TEXT_MUTED,
            font=ctk.CTkFont(size=11),
        ).pack(side="left", padx=(0, 4))

        ctk.CTkButton(
            ctrl, text="↑", width=28, height=24,
            fg_color=T.BADGE_BG, hover_color=T.ACCENT_HOVER,
            text_color=T.TEXT_HEAD,
            font=ctk.CTkFont(size=11),
            command=lambda c=card: self._move_section(c, -1),
        ).pack(side="left", padx=2)
        ctk.CTkButton(
            ctrl, text="↓", width=28, height=24,
            fg_color=T.BADGE_BG, hover_color=T.ACCENT_HOVER,
            text_color=T.TEXT_HEAD,
            font=ctk.CTkFont(size=11),
            command=lambda c=card: self._move_section(c, 1),
        ).pack(side="left", padx=2)
        ctk.CTkButton(
            ctrl, text="✕", width=28, height=24,
            fg_color=T.DANGER, hover_color=T.DANGER_HOVER,
            text_color=T.TEXT_HEAD,
            font=ctk.CTkFont(size=11),
            command=lambda c=card: self._remove_section(c),
        ).pack(side="left", padx=(4, 0))

        body = ctk.CTkFrame(card, fg_color="transparent")
        body.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 10))
        body.grid_columnconfigure(0, weight=1)

        def lbl(text): 
            ctk.CTkLabel(body, text=text, text_color=T.TEXT_MUTED,
                         font=ctk.CTkFont(size=11)).pack(anchor="w")
        def entry(var, ph=""):
            e = ctk.CTkEntry(body, textvariable=var, placeholder_text=ph,
                             fg_color=T.BG_INNER, border_color=T.BG_BORDER,
                             text_color=T.TEXT_HEAD,
                             placeholder_text_color=T.TEXT_DIM)
            e.pack(fill="x", pady=(2,6))
            return e
        def textarea(height=60):
            t = ctk.CTkTextbox(body, height=height, fg_color=T.BG_INNER,
                               text_color=T.TEXT_HEAD,
                               border_color=T.BG_BORDER, border_width=1)
            t.pack(fill="x", pady=(2,6))
            return t

        sec_entry = {
            "type": stype, "data": data, "frame": card,
            "body": body, "visible_var": visible_var, "title_label": title_lbl,
        }

        if stype == "banner":
            v = ctk.StringVar()
            lbl("Image URL (paste any image link)")
            entry(v, "https://example.com/banner.jpg")
            v.trace_add("write", lambda *_: self._schedule_preview())
            data["_url_var"] = v

        elif stype == "youtube":
            v = ctk.StringVar()
            v.trace_add("write", lambda *_: self._schedule_preview())
            lbl("YouTube video link")
            entry(v, "https://youtube.com/watch?v=...")
            ctk.CTkLabel(body, text="▶ Video will play inside the card",
                         text_color=T.ACCENT, font=ctk.CTkFont(size=11)).pack(anchor="w")
            data["_url_var"] = v

        elif stype == "text":
            v = ctk.StringVar()
            sv = ctk.StringVar(value="medium")
            av = ctk.StringVar(value="left")
            lbl("Text content")
            t = textarea(70)
            rr = ctk.CTkFrame(body, fg_color="transparent")
            rr.pack(fill="x")
            ctk.CTkLabel(rr,text="Size:",text_color=T.TEXT_MUTED,
                         font=ctk.CTkFont(size=11)).grid(row=0,column=0,padx=(0,4))
            for i2,s2 in enumerate(["small","medium","large","heading"]):
                ctk.CTkButton(rr,text=s2,width=1,
                              fg_color=T.BADGE_BG,hover_color=T.ACCENT_HOVER,
                              text_color=T.TEXT_HEAD,
                              font=ctk.CTkFont(size=9),
                              command=lambda s=s2,sv=sv: sv.set(s)).grid(
                    row=0,column=i2+1,padx=2)
                rr.grid_columnconfigure(i2+1,weight=1)
            data["_text_box"] = t
            data["_size_var"] = sv
            data["_align_var"] = av

        elif stype == "features":
            lbl("Features (one per line, emoji optional)")
            t = textarea(80)
            t.insert("1.0","✅ Feature one\n✅ Feature two\n✅ Feature three")
            data["_box"] = t

        elif stype == "price":
            pv  = ctk.StringVar(value="$89")
            opv = ctk.StringVar(value="$129")
            nv  = ctk.StringVar(value="One-time · Lifetime")
            rr  = ctk.CTkFrame(body,fg_color="transparent")
            rr.pack(fill="x")
            rr.grid_columnconfigure((0,1),weight=1)
            ctk.CTkLabel(rr,text="Price",text_color=T.TEXT_MUTED,
                         font=ctk.CTkFont(size=11)).grid(row=0,column=0,sticky="w",padx=2)
            ctk.CTkLabel(rr,text="Old price",text_color=T.TEXT_MUTED,
                         font=ctk.CTkFont(size=11)).grid(row=0,column=1,sticky="w",padx=2)
            ctk.CTkEntry(rr,textvariable=pv,fg_color=T.BG_INNER,
                         border_color=T.BG_BORDER,text_color=T.TEXT_HEAD,
                         placeholder_text_color=T.TEXT_DIM).grid(row=1,column=0,sticky="ew",padx=2,pady=(2,4))
            ctk.CTkEntry(rr,textvariable=opv,fg_color=T.BG_INNER,
                         border_color=T.BG_BORDER,text_color=T.TEXT_HEAD,
                         placeholder_text_color=T.TEXT_DIM).grid(row=1,column=1,sticky="ew",padx=2,pady=(2,4))
            lbl("Price note")
            entry(nv,"e.g. One-time · Lifetime")
            data["_price"]=pv; data["_old"]=opv; data["_note"]=nv

        elif stype == "links":
            link_kinds = [
                ("buy", "🛒 Buy / Gumroad Link", "https://gumroad.com/l/your-product"),
                ("youtube", "▶️ YouTube", "https://youtube.com/@faraz"),
                ("linkedin", "💼 LinkedIn", "https://linkedin.com/in/..."),
                ("github", "🐙 GitHub", "https://github.com/farazgoal-boop"),
                ("website", "🌐 Website", "https://muhammad-faraz-dev.netlify.app"),
            ]
            link_vars = []
            for kind, lbl_txt, ph in link_kinds:
                ctk.CTkLabel(body, text=lbl_txt, text_color=T.TEXT_MUTED,
                             font=ctk.CTkFont(size=11)).pack(anchor="w")
                v2 = ctk.StringVar()
                ctk.CTkEntry(body, textvariable=v2, placeholder_text=ph,
                             fg_color=T.BG_INNER, border_color=T.BG_BORDER,
                             text_color=T.TEXT_HEAD,
                             placeholder_text_color=T.TEXT_DIM).pack(
                    fill="x", pady=(2, 4))
                v2.trace_add("write", lambda *_: self._schedule_preview())
                if kind == "buy":
                    self._buy_var = v2
                link_vars.append((kind, lbl_txt.split(" ", 1)[-1] if " " in lbl_txt else lbl_txt, v2))
            data["_link_vars"] = link_vars

        elif stype == "contact":
            ctk.CTkLabel(body,
                         text="Contact footer uses your info from App Identity above.",
                         text_color=T.ACCENT,
                         font=ctk.CTkFont(size=11)).pack(anchor="w",pady=4)

        self._sections.append(sec_entry)
        self._renumber_sections()
        self._schedule_preview()

    def _renumber_sections(self) -> None:
        """Refresh section number labels after reorder."""
        for index, sec in enumerate(self._sections):
            if not sec["frame"].winfo_exists():
                continue
            label = next((lbl for lbl, t in SECTION_TYPES if t == sec["type"]), sec["type"])
            title = sec.get("title_label")
            if title and title.winfo_exists():
                title.configure(text=f"Section {index + 1}: {label}")

    def _move_section(self, card_widget, direction: int) -> None:
        """Move a section up (-1) or down (+1) in the list."""
        indices = [i for i, s in enumerate(self._sections) if s["frame"] == card_widget]
        if not indices:
            return
        index = indices[0]
        new_index = index + direction
        if new_index < 0 or new_index >= len(self._sections):
            return
        self._sections[index], self._sections[new_index] = (
            self._sections[new_index], self._sections[index],
        )
        for row, sec in enumerate(self._sections):
            if sec["frame"].winfo_exists():
                sec["frame"].grid(row=row, column=0, sticky="ew", pady=(0, 6), padx=2)
        self._sec_row = len(self._sections)
        self._renumber_sections()
        self._schedule_preview()

    def _remove_section(self, card_widget) -> None:
        card_widget.destroy()
        self._sections = [s for s in self._sections if s["frame"] != card_widget]
        self._sec_row = len(self._sections)
        self._renumber_sections()
        self._schedule_preview()

    # ─── Collect data from sections ───────────────────────────────────────────

    def _collect_sections(self) -> list:
        result = []
        for sec in self._sections:
            if not sec["frame"].winfo_exists():
                continue
            if not sec.get("visible_var", ctk.BooleanVar(value=True)).get():
                continue
            stype = sec["type"]
            data  = sec["data"]
            d     = {}

            if stype == "banner":
                d["url"] = data.get("_url_var", ctk.StringVar()).get()
            elif stype == "youtube":
                d["url"] = data.get("_url_var", ctk.StringVar()).get()
            elif stype == "text":
                tb = data.get("_text_box")
                d["content"] = tb.get("1.0","end").strip() if tb else ""
                d["size"]    = data.get("_size_var", ctk.StringVar(value="medium")).get()
                d["align"]   = data.get("_align_var", ctk.StringVar(value="left")).get()
            elif stype == "features":
                tb = data.get("_box")
                d["items"] = tb.get("1.0","end").strip() if tb else ""
            elif stype == "price":
                d["price"]     = data.get("_price", ctk.StringVar()).get()
                d["old_price"] = data.get("_old",   ctk.StringVar()).get()
                d["note"]      = data.get("_note",  ctk.StringVar()).get()
            elif stype == "links":
                d["links"] = [
                    {"kind": kind, "label": label, "url": _clean_url(v.get())}
                    for kind, label, v in data.get("_link_vars", [])
                ]
            elif stype == "contact":
                pass   # uses meta

            result.append({"type": stype, "data": d})
        return result

    def _apply_card_template(self, name: str) -> None:
        """Apply a built-in visual card template."""
        self._style_name = name
        style = CARD_STYLE_TEMPLATES.get(name, CARD_STYLE_TEMPLATES["Dark Premium"])
        self._accent = style.get("accent", self._accent)
        self._schedule_preview()

    def _collect_buy_link(self) -> str:
        """Resolve Gumroad/buy URL from links section."""
        if hasattr(self, "_buy_var"):
            url = _clean_url(self._buy_var.get())
            if url:
                return url
        for sec in self._sections:
            if sec.get("type") != "links":
                continue
            for kind, _label, var in sec["data"].get("_link_vars", []):
                if kind == "buy":
                    url = _clean_url(var.get())
                    if url:
                        return url
        return ""

    def _collect_meta(self) -> dict:
        return {
            "app_name": self._mname.get().strip(),
            "icon":     self._micon.get().strip() or "⭐",
            "tagline":  self._mtag.get().strip(),
            "accent":   self._accent,
            "org":      self._meta.get("org", "Faraz Automation"),
            "wa":       self._meta.get("wa", "+92 316 2400657"),
            "email":    self._meta.get("email", "farazgoal@gmail.com"),
            "addr":     self._meta.get("addr", "Karachi, Pakistan"),
            "style":    CARD_STYLE_TEMPLATES.get(self._style_name, CARD_STYLE_TEMPLATES["Dark Premium"]),
            "buy_link": self._collect_buy_link(),
        }

    def _get_export_html(self) -> str:
        """Full HTML for browser export, save, and bulk send (real iframes)."""
        secs = self._collect_sections()
        meta = self._collect_meta()
        meta["accent"] = self._accent
        return generate_html(secs, meta, for_preview=False)

    # ─── Generate ─────────────────────────────────────────────────────────────

    def _ensure_html_frame(self) -> bool:
        """Lazily create HtmlFrame on first preview (avoids startup crashes)."""
        if self._html_frame is not None:
            return True
        if not HAS_HTML_PREVIEW:
            return False
        try:
            self._preview_fallback.pack_forget()
            self._html_frame = HtmlFrame(self._preview_host, messages_enabled=False)
            self._html_frame.pack(fill="both", expand=True)
            return True
        except Exception as exc:
            logger.warning("HtmlFrame init failed: %s", exc)
            self._html_frame = None
            return False

    def _schedule_preview(self) -> None:
        """Debounced live preview update (500 ms)."""
        if self._preview_job is not None:
            self.after_cancel(self._preview_job)
        self._preview_job = self.after(500, self._update_live_preview)

    def _update_live_preview(self) -> None:
        """Render card HTML into embedded browser widget."""
        self._preview_job = None
        try:
            secs = self._collect_sections()
            meta = self._collect_meta()
            meta["accent"] = self._accent
            preview_html = generate_html(secs, meta, for_preview=True)
            if self._ensure_html_frame():
                self._html_frame.load_html(preview_html)
                self._preview_fallback.pack_forget()
            self._status.set(f"✅ Live preview · {len(secs)} sections · {len(preview_html)} chars")
        except Exception as exc:
            logger.exception("Preview update failed")
            self._status.set(f"Preview error: {exc}")

    def _generate(self):
        self._html = self._get_export_html()
        self._update_live_preview()

    def _open_browser(self):
        self._html = self._get_export_html()
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".html",
                                          mode="w", encoding="utf-8")
        tmp.write(self._html)
        tmp.close()
        webbrowser.open(f"file://{tmp.name}")

    def _save_html(self):
        self._html = self._get_export_html()
        name = self._mname.get().strip().replace(" ","_") or "card"
        path = filedialog.asksaveasfilename(
            defaultextension=".html",
            filetypes=[("HTML","*.html")],
            initialfile=f"{name}_card.html")
        if path:
            Path(path).write_text(self._html, encoding="utf-8")
            self._status.set(f"✅ Saved: {Path(path).name}")

    # ─── Bulk Send dialog ─────────────────────────────────────────────────────

    def _show_bulk_send(self):
        if not self._html:
            self._generate()

        if self.main_window is None:
            messagebox.showerror("Unavailable", "Bulk send requires the main app window.")
            return

        dlg = ctk.CTkToplevel(self)
        dlg.title("Bulk Send Card")
        dlg.geometry("560x780")
        dlg.grab_set()
        dlg.configure(fg_color=T.BG_MAIN)
        dlg.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(dlg, text="📤  Bulk Send Card (AI-personalized)",
                     font=ctk.CTkFont(size=18,weight="bold"),
                     text_color=T.TEXT_HEAD).grid(
            row=0,column=0,padx=20,pady=(20,4),sticky="w")

        def _step_header(parent, num, text):
            row = ctk.CTkFrame(parent, fg_color="transparent")
            row.grid(row=0, column=0, columnspan=2, padx=14, pady=(12, 6), sticky="w")
            ctk.CTkLabel(row, text=str(num), fg_color=T.ACCENT, corner_radius=12,
                         width=24, height=24, text_color=T.TEXT_HEAD,
                         font=ctk.CTkFont(size=11, weight="bold")).pack(side="left")
            ctk.CTkLabel(row, text=text, font=ctk.CTkFont(size=13, weight="bold"),
                         text_color=T.TEXT_HEAD).pack(side="left", padx=(8, 0))

        def _pill(parent, text, fg=None, text_color=None):
            return ctk.CTkLabel(parent, text=text, fg_color=fg or T.BADGE_BG,
                                 corner_radius=999, text_color=text_color or T.TEXT_MUTED,
                                 font=ctk.CTkFont(size=11, weight="bold"), padx=10, pady=4)

        # Step 1 — Import contacts
        cf = ctk.CTkFrame(dlg,fg_color=T.BG_SURFACE,corner_radius=14,
                           border_width=1,border_color=T.BG_BORDER)
        cf.grid(row=1,column=0,padx=20,pady=(0,10),sticky="ew")
        cf.grid_columnconfigure(0,weight=1)
        _step_header(cf, 1, "Import Contacts (CSV/Excel/HTML)")

        count_var = ctk.StringVar(value="No contacts loaded")
        ctk.CTkLabel(cf,textvariable=count_var,text_color=T.TEXT_MUTED,
                     font=ctk.CTkFont(size=11)).grid(
            row=1,column=0,padx=14,pady=(0,6),sticky="w")

        self._bulk_contacts: List[Contact] = []
        self._bulk_messages: Dict[str, str] = {}

        def import_contacts():
            path = filedialog.askopenfilename(
                title="Import Contacts",
                filetypes=[("All","*.csv *.xls *.xlsx *.html *.htm"),
                           ("CSV","*.csv"),("Excel","*.xls *.xlsx")])
            if not path:
                return
            try:
                result = UniversalDataImporter().import_file(path)
                self._bulk_contacts = _rows_to_contacts(result.contacts)
                self._bulk_messages = {}
                skipped = len(result.contacts) - len(self._bulk_contacts)
                count_var.set(
                    f"✅ {len(self._bulk_contacts)} contacts loaded"
                    + (f" ({skipped} skipped — no valid phone/email)" if skipped else ""))
                _set_ai_status("Not generated yet")
            except Exception as ex:
                messagebox.showerror("Error", str(ex), parent=dlg)

        ctk.CTkButton(cf,text="📂 Import Contacts",
                      fg_color=T.ACCENT, hover_color=T.ACCENT_HOVER,
                      text_color=T.TEXT_HEAD,
                      command=import_contacts).grid(
            row=2,column=0,padx=14,pady=(0,12),sticky="ew")

        # Channel selection
        ch = ctk.CTkFrame(dlg,fg_color=T.BG_SURFACE,corner_radius=14,
                           border_width=1,border_color=T.BG_BORDER)
        ch.grid(row=2,column=0,padx=20,pady=(0,10),sticky="ew")
        ch.grid_columnconfigure((0,1),weight=1)
        _step_header(ch, 2, "Channel & Consent")

        channel_var = ctk.StringVar(value="whatsapp")
        ctk.CTkRadioButton(ch,text="📱 WhatsApp",
                           variable=channel_var,value="whatsapp",
                           text_color=T.TEXT_MUTED).grid(
            row=1,column=0,padx=14,pady=(0,8),sticky="w")
        ctk.CTkRadioButton(ch,text="📧 Email (HTML card)",
                           variable=channel_var,value="email",
                           text_color=T.TEXT_MUTED).grid(
            row=1,column=1,padx=14,pady=(0,8),sticky="w")

        consent_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(ch, text="I have consent from these contacts to message them",
                         variable=consent_var, text_color=T.TEXT_MUTED,
                         font=ctk.CTkFont(size=11)).grid(
            row=2,column=0,columnspan=2,padx=14,pady=(0,12),sticky="w")

        # Step 3 — AI personalization
        af = ctk.CTkFrame(dlg,fg_color=T.BG_SURFACE,corner_radius=14,
                           border_width=1,border_color=T.BG_BORDER)
        af.grid(row=4,column=0,padx=20,pady=(0,10),sticky="ew")
        af.grid_columnconfigure(0,weight=1)
        _step_header(af, 3, "🤖 AI Personalization")
        ai_status_pill = _pill(af, "Not generated yet")
        ai_status_pill.grid(row=1,column=0,padx=14,pady=(0,10),sticky="w")

        def _set_ai_status(text, fg=None, text_color=None):
            ai_status_pill.configure(text=text, fg_color=fg or T.BADGE_BG,
                                      text_color=text_color or T.TEXT_MUTED)

        def generate_personalization():
            if not self._bulk_contacts:
                messagebox.showwarning("No Contacts","Import contacts first.",parent=dlg)
                return
            api_key = self.main_window._ai_api_key.get()
            if not api_key:
                messagebox.showwarning("No API key",
                    "Add your Anthropic API key in Settings → AI Cards first.", parent=dlg)
                return

            desc_box = next(
                (s["data"].get("_text_box") for s in self._sections if s["type"] == "text"), None)
            features_box = next(
                (s["data"].get("_box") for s in self._sections if s["type"] == "features"), None)
            card_summary = {
                "tagline": self._mtag.get(),
                "description": desc_box.get("1.0", "end").strip() if desc_box else "",
                "features": [
                    line.strip(" ✅")
                    for line in (features_box.get("1.0", "end") if features_box else "").splitlines()
                    if line.strip()
                ],
            }
            channel = channel_var.get()
            contact_dicts = [
                {"key": _contact_key(c), "name": c.name, "phone": c.phone,
                 "email": c.email, "custom_fields": c.custom_fields}
                for c in self._bulk_contacts if _contact_key(c)
            ]

            btn_ai.configure(state="disabled")
            _set_ai_status("Personalizing messages…")

            def _ai_failed(msg):
                btn_ai.configure(state="normal")
                _set_ai_status(f"⚠ {msg}", fg=T.BADGE_BG, text_color=T.DANGER_ON_BADGE)

            def _ai_done(messages):
                self._bulk_messages = messages
                btn_ai.configure(state="normal")
                missing = len(self._bulk_contacts) - len(messages)
                if missing:
                    _set_ai_status(
                        f"✅ Personalized {len(messages)}/{len(self._bulk_contacts)} — "
                        f"{missing} skipped (generation failed)",
                        fg=T.BADGE_BG, text_color=T.DANGER_ON_BADGE)
                else:
                    _set_ai_status(
                        f"✅ Personalized {len(messages)}/{len(self._bulk_contacts)} contacts",
                        fg=T.BADGE_BG, text_color=T.SUCCESS)

            def worker():
                try:
                    messages = ai_service.generate_personalized_messages(
                        card_summary, contact_dicts, api_key, channel)
                except AIServiceError as ex:
                    dlg.after(0, lambda: _ai_failed(str(ex)))
                    return
                dlg.after(0, lambda: _ai_done(messages))

            threading.Thread(target=worker, daemon=True).start()

        btn_ai = ctk.CTkButton(af, text="✨ Generate personalized messages",
                                fg_color=T.ACCENT, hover_color=T.ACCENT_HOVER,
                                text_color=T.TEXT_HEAD,
                                command=generate_personalization)
        btn_ai.grid(row=2,column=0,padx=14,pady=(0,12),sticky="ew")

        # Step 4 — Review & send
        pf = ctk.CTkFrame(dlg,fg_color=T.BG_SURFACE,corner_radius=14,
                           border_width=1,border_color=T.BG_BORDER)
        pf.grid(row=5,column=0,padx=20,pady=(0,10),sticky="ew")
        pf.grid_columnconfigure(0,weight=1)
        _step_header(pf, 4, "Review & Send")

        prog = ctk.CTkProgressBar(pf,progress_color=T.SUCCESS)
        prog.grid(row=1,column=0,padx=14,pady=(0,4),sticky="ew")
        prog.set(0)
        prog_lbl = ctk.CTkLabel(pf,text="Ready.",
                                 text_color=T.TEXT_MUTED,font=ctk.CTkFont(size=11))
        prog_lbl.grid(row=2,column=0,padx=14,pady=(0,12),sticky="w")

        stop_flag = threading.Event()

        def log_entry(to, channel, status):
            self._send_log.insert(0, {
                "time": datetime.now().strftime("%H:%M:%S"),
                "to": to, "channel": channel, "status": status, "read": False,
            })

        def do_send():
            if not self._bulk_contacts:
                messagebox.showwarning("No Contacts","Import contacts first.",parent=dlg)
                return
            if self.main_window.consent_required_var.get() and not consent_var.get():
                messagebox.showwarning("Consent Required",
                    "Confirm recipient consent before sending.", parent=dlg)
                return
            sendable = [c for c in self._bulk_contacts if _contact_key(c) in self._bulk_messages]
            if not sendable:
                messagebox.showwarning("No Messages",
                    "Generate personalized messages first.", parent=dlg)
                return
            if len(sendable) > self.main_window.daily_limit_var.get():
                messagebox.showwarning("Daily Limit",
                    "Contacts to send exceed the configured daily limit "
                    "(Settings → Campaign Safety).", parent=dlg)
                return
            if not messagebox.askyesno("Confirm",
                f"Send AI-personalized card to {len(sendable)} contacts via "
                f"{channel_var.get()}?", parent=dlg):
                return

            stop_flag.clear()
            btn_send.configure(state="disabled")
            btn_stop.configure(state="normal")
            channel = channel_var.get()
            total = len(sendable)

            def worker():
                sent = failed = 0
                if channel == "whatsapp":
                    messages = [self._bulk_messages[_contact_key(c)] for c in sendable]

                    def progress_cb(current, total_, description):
                        def upd():
                            prog.set(current / total_ if total_ else 0)
                            prog_lbl.configure(text=f"{description} ({current}/{total_})")
                        dlg.after(0, upd)

                    def event_cb(kind, payload):
                        if kind == "message":
                            log_entry(payload.get("phone", ""), "whatsapp",
                                      payload.get("status", "unknown"))

                    try:
                        result = self.main_window.whatsapp_sender.send_messages(
                            contacts=sendable, messages=messages,
                            delay=self.main_window.delay_var.get(),
                            use_jitter=self.main_window.jitter_var.get(),
                            max_messages=self.main_window.daily_limit_var.get(),
                            progress_callback=progress_cb, event_callback=event_cb,
                        )
                        sent, failed = result.get("sent", 0), result.get("failed", 0)
                    except Exception as ex:
                        failed = total
                        dlg.after(0, lambda: messagebox.showerror(
                            "Send failed", str(ex), parent=dlg))
                else:
                    meta = self._collect_meta()
                    recipients = []
                    for c in sendable:
                        body_text = self._bulk_messages[_contact_key(c)]
                        html_body = (
                            "<html><body style='font-family:sans-serif;line-height:1.6;"
                            f"color:#222'><p>{safe_text(body_text).replace(chr(10), '<br>')}</p>"
                            "<hr style='border:none;border-top:1px solid #ddd'>"
                            f"<p style='font-size:12px;color:#888'>{safe_text(meta['app_name'])}"
                            f" · {safe_text(meta['org'])}</p></body></html>"
                        )
                        subject = (f"{meta['app_name']} — {meta['tagline']}"
                                   if meta['tagline'] else meta['app_name'])
                        recipients.append((c, subject, html_body))

                    def progress_cb(sent_n, failed_n, total_, to_addr):
                        def upd():
                            prog.set((sent_n + failed_n) / total_ if total_ else 0)
                            prog_lbl.configure(text=f"Sent → {to_addr} ({sent_n + failed_n}/{total_})")
                            log_entry(to_addr, "email", "sent")
                        dlg.after(0, upd)

                    try:
                        result = self.main_window._send_email_campaign(
                            recipients, f"AI Card — {meta['app_name']}",
                            progress_callback=progress_cb, stop_flag=stop_flag)
                        sent, failed = result["sent"], result["failed"]
                    except Exception as ex:
                        failed = total
                        dlg.after(0, lambda: messagebox.showerror(
                            "Send failed", str(ex), parent=dlg))

                def finish():
                    btn_send.configure(state="normal")
                    btn_stop.configure(state="disabled")
                    prog.set(1)
                    prog_lbl.configure(text=f"Done! Sent: {sent}  Failed: {failed}")
                    self._refresh_stats()
                    show_toast(self.main_window, f"Campaign done — {sent} sent, {failed} failed.",
                               kind="success" if failed == 0 else "error")
                dlg.after(0, finish)

            threading.Thread(target=worker,daemon=True).start()

        def do_stop():
            stop_flag.set()
            prog_lbl.configure(text="Stopping...")

        btn_row = ctk.CTkFrame(dlg,fg_color="transparent")
        btn_row.grid(row=6,column=0,padx=20,pady=(0,20),sticky="ew")
        btn_row.grid_columnconfigure(0,weight=1)
        btn_send = ctk.CTkButton(btn_row,text="🚀 Start Sending",
                                  fg_color=T.SUCCESS,hover_color=T.SUCCESS,
                                  text_color=T.TEXT_HEAD,
                                  command=do_send)
        btn_send.grid(row=0,column=0,sticky="ew",padx=(0,6))
        btn_stop = ctk.CTkButton(btn_row,text="⏹ Stop",
                                  fg_color=T.DANGER,hover_color=T.DANGER_HOVER,
                                  text_color=T.TEXT_HEAD,
                                  state="disabled",command=do_stop)
        btn_stop.grid(row=0,column=1,sticky="ew")

    # ─── Stats ────────────────────────────────────────────────────────────────

    def _refresh_stats(self):
        total  = len(self._send_log)
        sent   = sum(1 for l in self._send_log if l["status"]=="sent")
        read   = sum(1 for l in self._send_log if l.get("read"))
        unread = sent - read

        self._stat_vars["total"].set(str(total))
        self._stat_vars["sent"].set(str(sent))
        self._stat_vars["read"].set(str(read))
        self._stat_vars["unread"].set(str(unread))

        today = date.today().strftime("%d %b")
        lines = [f"── {today} ──"]
        for entry in self._send_log[:20]:
            mark = "✅" if entry.get("read") else "📨"
            lines.append(
                f"{mark} {entry['time']}  {entry['channel'].upper():<10}  "
                f"{entry['to'][:20]:<20}  {entry['status']}")

        self._log_box.configure(state="normal")
        self._log_box.delete("1.0","end")
        self._log_box.insert("1.0", "\n".join(lines) if lines else "No sends yet.")
        self._log_box.configure(state="disabled")

    # ─── Helpers ──────────────────────────────────────────────────────────────

    def _set_accent(self, h: str):
        self._accent = h

    def _custom_color(self):
        c = colorchooser.askcolor(title="Pick color", color=self._accent)
        if c and c[1]:
            self._accent = c[1]

    def _generate_card_with_ai(self) -> None:
        if self.main_window is None:
            messagebox.showwarning("Unavailable", "AI generation isn't available in this context.")
            return
        api_key = self.main_window._ai_api_key.get()
        if not api_key:
            messagebox.showwarning(
                "No API key",
                "Add your Anthropic API key in Settings → AI Cards before generating.")
            return
        description = self._ai_desc_box.get("1.0", "end").strip()
        if not description:
            messagebox.showwarning("Describe your product", "Enter a short product description first.")
            return

        self._ai_generate_btn.configure(state="disabled")
        self._ai_status_var.set("Generating…")

        def worker():
            try:
                data = ai_service.generate_card_copy(
                    description, api_key, list(CARD_STYLE_TEMPLATES.keys()))
            except AIServiceError as ex:
                self.after(0, lambda: self._on_ai_generate_failed(str(ex)))
                return
            self.after(0, lambda: self._apply_ai_card_copy(data))

        threading.Thread(target=worker, daemon=True).start()

    def _on_ai_generate_failed(self, message: str) -> None:
        self._ai_generate_btn.configure(state="normal")
        self._ai_status_var.set("")
        messagebox.showerror("AI generation failed", message)

    def _apply_ai_card_copy(self, data: dict) -> None:
        self._ai_generate_btn.configure(state="normal")
        self._ai_status_var.set("✅ Generated — review and adjust below.")

        features = data.get("features") or []
        APP_PRESETS["Custom"] = {
            "icon": data.get("icon") or "⭐",
            "tagline": data.get("tagline", ""),
            "accent": APP_PRESETS["Custom"].get("accent", "#6c63ff"),
            "description": data.get("description", ""),
            "features": "\n".join(f"✅ {f}" for f in features),
            "price": data.get("price", ""),
            "old_price": data.get("old_price", ""),
            "price_note": data.get("price_note", ""),
        }
        self._load_preset("Custom")

        style_name = data.get("style_name")
        if style_name in CARD_STYLE_TEMPLATES:
            self._template_var.set(style_name)
            self._apply_card_template(style_name)

    def _load_preset(self, name: str):
        preset = APP_PRESETS.get(name, {})
        self._mname.set(name)
        self._micon.set(preset.get("icon","⭐"))
        self._mtag.set(preset.get("tagline",""))
        if preset.get("accent"):
            self._accent = preset["accent"]
        for n2, btn in self._app_btns.items():
            btn.configure(
                fg_color=T.ACCENT if n2==name else T.BADGE_BG,
                hover_color=T.ACCENT_HOVER if n2==name else T.BG_BORDER)
        # Clear and add default sections for preset
        for sec in list(self._sections):
            if sec["frame"].winfo_exists():
                sec["frame"].destroy()
        self._sections.clear()
        self._sec_row = 0
        # Add sensible defaults
        self._add_section("banner")
        self._add_section("text")
        self._add_section("features")
        self._add_section("price")
        self._add_section("links")
        self._add_section("contact")
        # Pre-fill text + features
        for sec in self._sections:
            if sec["type"]=="text":
                tb = sec["data"].get("_text_box")
                if tb:
                    tb.delete("1.0","end")
                    tb.insert("1.0", preset.get("description",""))
            elif sec["type"]=="features":
                tb = sec["data"].get("_box")
                if tb:
                    tb.delete("1.0","end")
                    tb.insert("1.0", preset.get("features",""))
            elif sec["type"]=="price":
                sec["data"].get("_price",ctk.StringVar()).set(preset.get("price",""))
                sec["data"].get("_old",  ctk.StringVar()).set(preset.get("old_price",""))
                sec["data"].get("_note", ctk.StringVar()).set(preset.get("price_note",""))
        self._status.set(f"Loaded: {name} — preview updating…")
        self._schedule_preview()


# ── Integration helper ────────────────────────────────────────────────────────

def build_card_creator_view(main_window) -> None:
    """
    Call inside MainWindow._create_ui() to register the Card Creator view.
    """
    frame = main_window._new_view_container("Cards", scrollable=False)
    frame.grid_rowconfigure(0, weight=1)
    frame.grid_columnconfigure(0, weight=1)
    tab = CardCreatorV2(frame, main_window=main_window)
    tab.grid(row=0, column=0, sticky="nsew")
    main_window.card_creator_tab = tab