"""
MessageCannon Pro — Card Creator V2
Complete in-app card builder with live HTML preview, section management,
bulk send via WhatsApp + Email, and read/unread tracking.
"""

import base64
import io
import logging
import mimetypes
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
from typing import Dict, List, Optional

from PIL import Image, ImageTk

from ..core import ai_service
from ..core.ai_service import AIServiceError
from ..models import Contact
from ..modules.data_importer import UniversalDataImporter
from ..utils.validators import DataValidator, PhoneValidator
from . import theme as T
from .toast import show_toast
from .window_utils import center_on_parent

logger = logging.getLogger(__name__)

try:
    from tkinterweb import HtmlFrame
    HAS_HTML_PREVIEW = True
except ImportError:
    HAS_HTML_PREVIEW = False
    logger.warning("tkinterweb not installed — card preview falls back to browser only")

try:
    from tkinterdnd2 import DND_FILES
    HAS_DND = True
except ImportError:
    HAS_DND = False


# ── Section types available in card builder ───────────────────────────────────
SECTION_TYPES = [
    ("🏷️ Header",          "header"),
    ("🖼️ Banner Image",    "banner"),
    ("▶️ YouTube Video",   "youtube"),
    ("📝 Text Block",      "text"),
    ("✅ Features List",   "features"),
    ("💰 Price Box",       "price"),
    ("🔗 Links Row",       "links"),
    ("📞 Contact Footer",  "contact"),
]

# Item 22 of the Live Testing Findings pass (Round 2): the canonical,
# sensible ordering new sections get auto-inserted into -- the same order
# SECTION_TYPES/_load_preset's own defaults already use (header first,
# footer last), so "Add Section" no longer requires manual reordering to
# get something coherent.
_SECTION_ORDER = [stype for _label, stype in SECTION_TYPES]

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


def _hex_or_fallback(value: Optional[str], fallback: str) -> str:
    """Returns `value` if it's a clean "#rrggbb" hex string, else `fallback`.
    Used only by the Item 11.3 template thumbnail gallery's tk.Canvas
    swatches, which can't render a CSS gradient/`url(...)` background
    (Gradient Bold, or a custom uploaded image) -- the real exported card
    is unaffected, this only governs a lightweight gallery-picker preview."""
    if isinstance(value, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", value.strip()):
        return value.strip()
    return fallback


def _clean_url(url: str) -> str:
    """Strip whitespace and stray surrounding quotes from pasted URLs."""
    return str(url).strip().strip('"').strip("'").strip()


def _contrast_text_color(hex_color: str) -> str:
    """Pick a readable body-text color (near-white or near-black) for a
    given solid background hex color, via relative luminance -- so a custom
    background someone picks light doesn't silently ship unreadable
    light-on-light text (the 6 built-in CARD_STYLE_TEMPLATES were each
    hand-paired with a matching text color; a custom background has no such
    pairing, so this stands in for that judgment)."""
    h = hex_color.lstrip("#")
    if len(h) != 6:
        return "rgba(255,255,255,0.85)"
    try:
        r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return "rgba(255,255,255,0.85)"
    luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
    return "rgba(20,20,20,0.85)" if luminance > 0.6 else "rgba(255,255,255,0.85)"


# Cards are standalone HTML files sent over WhatsApp/email -- embedding an
# uploaded image as a base64 data URI keeps the exported file self-contained
# (no broken links if the original file moves), but every extra MB roughly
# triples in encoded size and bloats the message. 5MB is generous for a
# banner/background image while still keeping the exported card a
# reasonable size to actually send.
MAX_UPLOAD_IMAGE_BYTES = 5 * 1024 * 1024


class ImageUploadError(Exception):
    """Raised by image_file_to_data_uri for a file that's missing, unreadable,
    too large, or not a recognized image type -- always caught and shown to
    the user via a toast, never left to surface as a raw traceback."""


def image_file_to_data_uri(path: str) -> str:
    """Read a local image file and return it as a base64 data: URI, so it
    can be used directly as an <img src="..."> in a standalone exported
    card with no external file dependency."""
    file_path = Path(path)
    if not file_path.is_file():
        raise ImageUploadError(f"File not found: {path}")

    size = file_path.stat().st_size
    if size > MAX_UPLOAD_IMAGE_BYTES:
        raise ImageUploadError(
            f"Image is {size / (1024*1024):.1f}MB — please use one under "
            f"{MAX_UPLOAD_IMAGE_BYTES // (1024*1024)}MB so the exported card "
            f"stays a reasonable size to send.")

    mime_type, _ = mimetypes.guess_type(str(file_path))
    if not mime_type or not mime_type.startswith("image/"):
        raise ImageUploadError(f"Not a recognized image file: {file_path.name}")

    encoded = base64.b64encode(file_path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def decode_data_uri_to_image(data_uri: str) -> Image.Image:
    """Decodes a base64 data: URI back into a PIL Image -- the inverse of
    image_file_to_data_uri, needed for the Item 11.1 live icon preview
    thumbnail and crop dialog."""
    _header, b64data = data_uri.split(",", 1)
    raw = base64.b64decode(b64data)
    return Image.open(io.BytesIO(raw)).convert("RGBA")


def crop_and_encode_image(source_img: Image.Image, crop_box: tuple, max_size: int = 256) -> str:
    """Crops `source_img` to `crop_box` (left, top, right, bottom) in the
    image's own real pixel coordinates, downsizes to at most `max_size` on
    a side, and returns a base64 PNG data: URI. Deliberately pure/Tk-free
    (no canvas or dialog state) so the actual crop math is directly unit-
    testable without simulating a mouse drag -- mouse-click automation is
    already documented elsewhere in this project as unreliable in this
    sandbox (see CLAUDE.md's Setup Wizard verification notes)."""
    cropped = source_img.crop(crop_box)
    cropped.thumbnail((max_size, max_size))
    buf = io.BytesIO()
    cropped.save(buf, format="PNG")
    encoded = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _parse_currency_value(text: str) -> Optional[float]:
    """Extracts the first numeric amount from a loosely-formatted price
    string (e.g. "$89", "Rs. 1,299.00", "$29/mo") -- returns None if no
    number is found, rather than raising, since these are free-text fields
    not a strict currency input."""
    match = re.search(r"[\d,]+\.?\d*", text or "")
    if not match:
        return None
    try:
        return float(match.group(0).replace(",", ""))
    except ValueError:
        return None


def compute_discount_percent(price: str, old_price: str) -> Optional[int]:
    """Item 11.4 of the Live Testing Findings pass (Round 2): auto-calculated
    discount % from the Sale Price / Original Price fields. Returns None
    (no badge shown) whenever either field doesn't parse to a real number,
    or the "sale" price isn't actually lower than the original -- a
    discount badge should never show something misleading."""
    new_val = _parse_currency_value(price)
    old_val = _parse_currency_value(old_price)
    if new_val is None or old_val is None or old_val <= 0 or new_val >= old_val:
        return None
    return round((1 - new_val / old_val) * 100)


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
    # Item 11.1 of the Live Testing Findings pass (Round 2): a real
    # drag-and-drop-uploaded logo image takes priority over the plain
    # emoji fallback when present.
    icon_image = meta.get("icon_image", "")
    tagline  = safe_text(meta.get("tagline", ""))
    org      = safe_text(meta.get("org", ""))
    wa       = safe_text(meta.get("wa", ""))
    email    = safe_text(meta.get("email", ""))
    addr     = safe_text(meta.get("addr", ""))
    style    = meta.get("style", CARD_STYLE_TEMPLATES["Dark Premium"])
    card_bg  = style.get("bg", "#1a1a2e")
    body_bg  = style.get("body_bg", "#111827")
    text_col = style.get("text", "rgba(255,255,255,0.85)")
    header_bg = style.get("header_bg", "#0a1628")
    if not meta.get("accent"):
        accent = style.get("accent", accent)
    buy_url = safe_attr(_clean_url(meta.get("buy_link", "").strip() or "#"))

    body_parts = []

    for sec in sections:
        stype = sec.get("type", "")
        data  = sec.get("data", {})

        if stype == "header":
            # Was previously hardcoded to always render first regardless of
            # `sections` -- now a real section like everything else
            # (addable/removable/reorderable), reading the same App
            # Name/Icon/Tagline identity fields from `meta` rather than its
            # own per-section data, since those are already global card
            # identity, not per-section content.
            org_line = (f'<div style="font-size:10px;color:rgba(255,255,255,0.4)">'
                        f'{org}</div>') if org else ""
            if icon_image:
                icon_html = (
                    f'<div style="width:44px;height:44px;border-radius:12px;overflow:hidden;flex-shrink:0">'
                    f'<img src="{safe_attr(icon_image)}" '
                    f'style="width:100%;height:100%;object-fit:cover;display:block"></div>'
                )
            else:
                icon_html = (
                    f'<div style="width:44px;height:44px;background:{accent};border-radius:12px;'
                    f'display:flex;align-items:center;justify-content:center;font-size:22px">{icon}</div>'
                )
            body_parts.append(f"""
    <div style="background:{header_bg};padding:20px 24px 0">
      <div style="height:3px;background:linear-gradient(90deg,{accent},{accent}88,{accent});
        margin:-20px -24px 20px;border-radius:20px 20px 0 0"></div>
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:16px">
        <div style="display:flex;align-items:center;gap:12px">
          {icon_html}
          <div>
            <div style="font-size:17px;font-weight:500;color:#fff">{app_name}</div>
            {org_line}
          </div>
        </div>
        <div style="font-size:10px;padding:4px 12px;border-radius:20px;
          background:rgba(255,255,255,0.08);color:rgba(255,255,255,0.6)">{tagline}</div>
      </div>
    </div>""")

        elif stype == "banner" and data.get("url"):
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
            # Item 11.5 of the Live Testing Findings pass (Round 2): the
            # purchase button's text/URL now live directly on the Price
            # section itself -- the "most important" part of the item's own
            # ask, since it removes the disconnect where the actual buy
            # button only worked if the user separately filled a "buy" link
            # in an unrelated Links section. Missing button_text/buy_url
            # keys (e.g. a hand-built `data` dict from before this section
            # had these fields) fall back to the pre-existing "BUY NOW" +
            # the meta-level buy_url (still resolved from the Links section
            # for backward compatibility) -- not a behavior change for any
            # existing caller that never used the new fields.
            button_label = safe_text((data.get("button_text") or "").strip() or "BUY NOW")
            section_url = _clean_url(data.get("buy_url", ""))
            effective_url = safe_attr(section_url) if section_url else buy_url
            # Item 11.4: a real, auto-calculated discount badge -- computed
            # by the caller (_collect_sections) via compute_discount_percent
            # and passed through as plain data, same as every other
            # pre-computed field this function already just renders.
            discount_pct = data.get("discount_percent")
            if price:
                old_html = f'<span style="font-size:12px;text-decoration:line-through;color:rgba(255,255,255,0.35);margin-left:8px">{old_price}</span>' if old_price else ""
                discount_html = (
                    f'<span style="font-size:11px;font-weight:700;color:#fff;background:{accent};'
                    f'padding:2px 9px;border-radius:10px;margin-left:8px">{discount_pct}% OFF</span>'
                ) if discount_pct else ""
                note_html = f'<div style="font-size:11px;color:rgba(255,255,255,0.45);margin-top:3px">{note}</div>' if note else ""
                buy_btn = (
                    f'<a href="{effective_url}" target="_blank" '
                    f'style="background:{accent};color:#fff;font-size:12px;font-weight:500;'
                    f'padding:9px 20px;border-radius:20px;cursor:pointer;text-decoration:none;'
                    f'display:inline-block">{button_label} →</a>'
                )
                body_parts.append(f"""
    <div style="margin:8px 24px;background:rgba(255,255,255,0.06);
      border:0.5px solid rgba(255,255,255,0.1);border-radius:12px;
      padding:14px 18px;display:flex;align-items:center;justify-content:space-between">
      <div>
        <div style="display:flex;align-items:baseline">
          <span style="font-size:28px;font-weight:500;color:{accent}">{price}</span>
          {old_html}{discount_html}
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
            org_html = (f'<div style="font-size:12px;font-weight:500;color:{accent};'
                        f'margin-bottom:6px">{org}</div>') if org else ""
            wa_html = (f'<div style="font-size:11px;color:rgba(255,255,255,0.5);'
                       f'margin-bottom:3px">📱 {wa}</div>') if wa else ""
            email_html = (f'<div style="font-size:11px;color:rgba(255,255,255,0.5);'
                          f'margin-bottom:3px">✉️ {email}</div>') if email else ""
            addr_html = (f'<div style="font-size:11px;color:rgba(255,255,255,0.4)">'
                         f'📍 {addr}</div>') if addr else ""
            if org_html or wa_html or email_html or addr_html:
                body_parts.append(f"""
    <div style="height:0.5px;background:rgba(255,255,255,0.08);margin:4px 24px"></div>
    <div style="padding:14px 24px 20px;display:flex;align-items:flex-end;justify-content:space-between">
      <div>
        {org_html}{wa_html}{email_html}{addr_html}
      </div>
      <div style="text-align:right">
        <div style="width:40px;height:40px;background:{accent}22;border:0.5px solid {accent}55;
          border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:20px">⊞</div>
        <div style="font-size:9px;color:rgba(255,255,255,0.2);margin-top:3px">QR Code</div>
      </div>
    </div>""")

    body_html = "\n".join(body_parts)
    title = f"{app_name} — {org}" if org else app_name
    footer_tag = f"Created with MessageCannon Pro · {org}" if org else "Created with MessageCannon Pro"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{background:{body_bg};font-family:Arial,Helvetica,sans-serif;
    min-height:100vh;display:flex;align-items:flex-start;
    justify-content:center;padding:20px}}
  /* Item 19 of the Live Testing Findings pass (Round 2): the in-app Live
     Card Preview panel showed significant blank space to the RIGHT of the
     card, not centered padding on both sides -- confirmed the root cause
     as the embedded preview renderer (tkinterweb.HtmlFrame, a lightweight
     pure-Python HTML/CSS engine, not a full browser engine) not honoring
     the body's `display:flex; justify-content:center` centering, so the
     unstyled outer <div> below just rendered as a normal left-aligned
     block at its natural width inside a wider viewport. .page below adds
     classic box-model centering (max-width + margin:0 auto) as a fallback
     that works regardless of flexbox support -- real browsers (Open in
     Browser / the saved .html export) already center via the flex rule
     above, so this is a redundant-but-harmless second centering mechanism
     there, and the actual fix for the in-app preview specifically. */
  .page{{max-width:560px;margin:0 auto}}
  .card{{width:100%;max-width:520px;background:{card_bg};
    border-radius:20px;overflow:hidden;
    border:0.5px solid rgba(255,255,255,0.08);
    box-shadow:0 20px 60px rgba(0,0,0,0.5)}}
  .footer-tag{{text-align:center;margin-top:10px;font-size:10px;
    color:rgba(255,255,255,0.2)}}
</style>
</head>
<body>
<div class="page">
  <div class="card">
{body_html}
  </div>
  <div class="footer-tag">{footer_tag}</div>
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
        # Custom background (task #6, Round 2 item 4): a separate style dict
        # from the 6 built-in CARD_STYLE_TEMPLATES (never touched -- see
        # Design System rules), selected via a "Custom" entry appended only
        # to the dropdown's *values* list, never inserted into the dict
        # itself. Starts as a plain dark default; either a color pick or an
        # uploaded image (see _pick_custom_bg_color/_pick_custom_bg_image)
        # overwrites it once the user actually customizes something.
        self._custom_style = {
            "bg": "#1a1a2e", "body_bg": "#1a1a2e",
            "text": "rgba(255,255,255,0.85)", "header_bg": "#1a1a2e",
        }
        self._buy_var = ctk.StringVar(value="")
        # Business/contact info shown in the card's footer -- previously a
        # dead, never-editable dict hardcoded to the developer's own real
        # contact details (org/phone/email/address), so every card any
        # MessageCannon user generated silently advertised the developer's
        # info instead of their own. Now real, empty-by-default StringVars
        # with a UI to edit them (see the "Your Contact Info" row below),
        # same pattern as the App Name/Icon/Tagline fields.
        self._morg   = ctk.StringVar(value="")
        self._mwa    = ctk.StringVar(value="")
        self._memail = ctk.StringVar(value="")
        self._maddr  = ctk.StringVar(value="")
        # Item 17 of the Live Testing Findings pass (Round 2): tracks
        # whether the card has any content a preset switch would silently
        # discard. Set True by _schedule_preview (called by essentially
        # every content-changing action already -- text/price/link/banner
        # edits, section add/remove/reorder, AI generation, accent/style
        # picks), then reset to False at the end of _load_preset itself
        # (undoing whatever got marked dirty by ITS OWN internal section-
        # building calls) -- so only genuine edits made *after* a preset
        # finishes loading count as "unsaved," not the load's own setup.
        self._card_dirty = False
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
        # Item 18 of the Live Testing Findings pass (Round 2): "top" (the
        # Card Identity panel) previously had no row weight at all -- it
        # just grew to its full natural height regardless of available
        # space, which was fine when it was small. Item 11 added enough
        # content to it (the logo drop zone, larger accent swatches, the
        # template thumbnail gallery, custom-background controls, contact
        # info fields) that its natural height now commonly exceeds the
        # visible window, with no scrollbar anywhere to reach the overflow
        # -- confirmed as the real cause, not guessed, by reading exactly
        # which grid row/weight config governed it. Both rows below now get
        # a real, bounded share of the available height and scroll their
        # own content independently. Deliberately NOT one merged outer
        # scroll region wrapping the sections list too -- that already has
        # its own working scrollable frame (_sections_scroll), and nesting
        # one scroll region inside another is an already-documented
        # anti-pattern in this codebase (see the Campaigns-home "Recent
        # Campaigns" fix elsewhere in CLAUDE.md).
        left.grid_rowconfigure(0, weight=3)
        left.grid_rowconfigure(1, weight=2)

        # ── Top: app selector + meta ──────────────────────────────────────────
        top = ctk.CTkScrollableFrame(left, fg_color=T.BG_SURFACE, corner_radius=14,
                            border_width=1, border_color=T.BG_BORDER)
        top.grid(row=0, column=0, sticky="nsew", pady=(0, 8))
        top.grid_columnconfigure(0, weight=1)
        self._card_identity_panel = top

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
                     corner_radius=999, text_color=T.ACCENT_TEXT,
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
                              command=lambda n=name: self._confirm_and_load_preset(n))
            b.grid(row=i//3, column=i%3, padx=3, pady=3, sticky="ew")
            bf.grid_columnconfigure(i%3, weight=1)
            self._app_btns[name] = b

        # Task #8 (Round 2 item 4): light visual grouping pass -- with the
        # AI box, presets, identity fields, style controls, and contact info
        # all now in one panel, a plain unlabeled stack of rows started to
        # read as one undifferentiated wall of fields. Small section labels
        # (same T.TEXT_DIM/10pt/bold style already used for "OR START FROM A
        # TEMPLATE" and "YOUR CONTACT INFO") group related controls without
        # a structural rebuild.
        ctk.CTkLabel(top, text="APP IDENTITY", text_color=T.TEXT_DIM,
                     font=ctk.CTkFont(size=10, weight="bold")).grid(
            row=4, column=0, padx=16, pady=(4, 4), sticky="w")

        # Meta fields row
        mf = ctk.CTkFrame(top, fg_color="transparent")
        mf.grid(row=5, column=0, padx=16, pady=(0, 8), sticky="ew")
        mf.grid_columnconfigure((0,1,2,3), weight=1)

        self._mname = ctk.StringVar(value="MessageCannon Pro")
        self._micon = ctk.StringVar(value="📨")
        self._mtag  = ctk.StringVar(value="Bulk Messaging Tool")
        # Item 11.1 of the Live Testing Findings pass (Round 2): a real
        # drag-and-drop logo upload, replacing the plain emoji text field as
        # the primary path -- self._micon_image_uri holds the uploaded/
        # cropped logo as a data: URI; self._micon (the emoji) remains the
        # fallback actually rendered in the exported card whenever no logo
        # has been uploaded (see generate_html's icon_image handling).
        self._micon_image_uri: Optional[str] = None

        for i,(lbl,var,ph) in enumerate([
            ("App Name", self._mname, "My App"),
            ("Tagline",  self._mtag,  "Short tagline"),
        ]):
            col = 0 if i == 0 else 2
            ctk.CTkLabel(mf, text=lbl, text_color=T.TEXT_MUTED,
                         font=ctk.CTkFont(size=11)).grid(row=0,column=col,sticky="w",padx=2)
            ctk.CTkEntry(mf, textvariable=var, placeholder_text=ph,
                         fg_color=T.BG_INNER, border_color=T.BG_BORDER,
                         text_color=T.TEXT_HEAD,
                         placeholder_text_color=T.TEXT_DIM,
                         font=ctk.CTkFont(size=11)).grid(
                row=1,column=col,sticky="ew",padx=2)
            var.trace_add("write", lambda *_: self._schedule_preview())

        ctk.CTkLabel(mf, text="Logo/Icon", text_color=T.TEXT_MUTED,
                     font=ctk.CTkFont(size=11)).grid(row=0, column=1, sticky="w", padx=2)
        self._build_icon_drop_zone(mf)

        ctk.CTkLabel(top, text="STYLE & APPEARANCE", text_color=T.TEXT_DIM,
                     font=ctk.CTkFont(size=10, weight="bold")).grid(
            row=6, column=0, padx=16, pady=(4, 4), sticky="w")

        # Item 11.3 of the Live Testing Findings pass (Round 2): larger
        # visual accent swatches, replacing the previous tiny 2-char-wide
        # tk.Button "dots" -- real 30x30px tk.Canvas squares (a Button's
        # width/height are text-cell units, not pixels, unless an image is
        # set; a Canvas gives genuine pixel control and a selection ring
        # that redraws, the same drawing technique _draw_nav_accent already
        # uses elsewhere in this app for a custom-painted element).
        cf = ctk.CTkFrame(top, fg_color="transparent")
        cf.grid(row=7, column=0, padx=16, pady=(0,12), sticky="w")
        ctk.CTkLabel(cf, text="Theme:", text_color=T.TEXT_MUTED,
                     font=ctk.CTkFont(size=11)).grid(row=0,column=0,padx=(0,8))
        self._accent_swatch_canvases: Dict[str, tk.Canvas] = {}
        for i,c in enumerate(ACCENT_COLORS):
            sw = tk.Canvas(cf, width=30, height=30, highlightthickness=0,
                            bg=T.resolve(T.BG_SURFACE), cursor="hand2")
            sw.grid(row=0, column=i+1, padx=3)
            sw.bind("<Button-1>", lambda _e, h=c: self._select_accent(h))
            self._accent_swatch_canvases[c] = sw
        ctk.CTkButton(cf, text="Custom…", width=70, height=30,
                      fg_color=T.BADGE_BG, hover_color=T.BG_BORDER,
                      text_color=T.TEXT_HEAD,
                      font=ctk.CTkFont(size=11),
                      command=self._custom_color).grid(row=0,column=len(ACCENT_COLORS)+1,padx=(6,0))
        self._redraw_accent_swatches()

        # Item 11.3: a real visual thumbnail gallery for Card Template,
        # replacing the plain-text CTkOptionMenu dropdown -- each thumbnail
        # is a small tk.Canvas painted with that template's own bg/header/
        # accent colors (a lightweight visual stand-in for a full HTML
        # render, which would be far too heavy to do once per template on
        # every rebuild). Gradient/image `body_bg` values (Gradient Bold,
        # or a custom uploaded background) can't be drawn on a plain
        # Canvas, so the swatch falls back to a flat neutral fill for
        # *this thumbnail only* -- the real exported card is unaffected,
        # this is purely a gallery-picker visual.
        ctk.CTkLabel(top, text="Card Template:", text_color=T.TEXT_MUTED,
                     font=ctk.CTkFont(size=11)).grid(
            row=8, column=0, padx=16, pady=(0, 4), sticky="w")
        gallery = ctk.CTkFrame(top, fg_color="transparent")
        gallery.grid(row=9, column=0, padx=16, pady=(0, 14), sticky="ew")
        self._template_var = ctk.StringVar(value="Dark Premium")
        self._template_var.trace_add("write", lambda *_: self._redraw_template_gallery())
        # "Custom" is appended only to the gallery here, never inserted into
        # CARD_STYLE_TEMPLATES itself (off-limits, see Design System rules)
        # -- _apply_card_template branches on it separately.
        gallery_names = list(CARD_STYLE_TEMPLATES.keys()) + ["Custom"]
        self._template_thumb_canvases: Dict[str, tk.Canvas] = {}
        self._template_thumb_labels: Dict[str, ctk.CTkLabel] = {}
        for i, name in enumerate(gallery_names):
            cell = ctk.CTkFrame(gallery, fg_color="transparent")
            cell.grid(row=(i // 4) * 2, column=i % 4, padx=4, pady=(0, 2))
            gallery.grid_columnconfigure(i % 4, weight=1)
            thumb = tk.Canvas(cell, width=88, height=54, highlightthickness=0,
                               bg=T.resolve(T.BG_SURFACE), cursor="hand2")
            thumb.pack()
            thumb.bind("<Button-1>", lambda _e, n=name: self._select_template(n))
            name_lbl = ctk.CTkLabel(gallery, text=name, text_color=T.TEXT_MUTED,
                                     font=ctk.CTkFont(size=9))
            name_lbl.grid(row=(i // 4) * 2 + 1, column=i % 4, pady=(0, 6))
            self._template_thumb_canvases[name] = thumb
            self._template_thumb_labels[name] = name_lbl
        self._redraw_template_gallery()

        # Custom background controls -- hidden unless "Custom" is the
        # selected template, so users don't see inactive controls.
        self._custom_bg_row = ctk.CTkFrame(top, fg_color="transparent")
        self._custom_bg_row.grid(row=9, column=0, padx=16, pady=(0, 14), sticky="ew")
        ctk.CTkLabel(self._custom_bg_row, text="Custom Background:",
                     text_color=T.TEXT_MUTED, font=ctk.CTkFont(size=11)).pack(
            side="left", padx=(0, 8))
        ctk.CTkButton(self._custom_bg_row, text="🎨 Pick Color", width=1,
                      fg_color=T.BADGE_BG, hover_color=T.BG_BORDER,
                      text_color=T.TEXT_HEAD, font=ctk.CTkFont(size=11),
                      command=self._pick_custom_bg_color).pack(side="left", padx=2)
        ctk.CTkButton(self._custom_bg_row, text="📁 Upload Image", width=1,
                      fg_color=T.BADGE_BG, hover_color=T.BG_BORDER,
                      text_color=T.TEXT_HEAD, font=ctk.CTkFont(size=11),
                      command=self._pick_custom_bg_image).pack(side="left", padx=2)
        ctk.CTkButton(self._custom_bg_row, text="✕ Clear image", width=1,
                      fg_color=T.BADGE_BG, hover_color=T.DANGER_HOVER,
                      text_color=T.TEXT_HEAD, font=ctk.CTkFont(size=11),
                      command=self._clear_custom_bg_image).pack(side="left", padx=2)
        self._custom_bg_status = ctk.StringVar(value="")
        ctk.CTkLabel(self._custom_bg_row, textvariable=self._custom_bg_status,
                     text_color=T.SUCCESS, font=ctk.CTkFont(size=10)).pack(
            side="left", padx=(8, 0))
        self._custom_bg_row.grid_remove()  # only shown when template == "Custom"

        # Your Contact Info -- shown in the card's Contact Footer section.
        # Previously hardcoded to the developer's own real phone/email/org
        # with no way to edit it at all, so every card any MessageCannon
        # user made advertised the developer's contact info instead of
        # their own. Empty by default; the Contact Footer section (see
        # SECTION_TYPES) simply omits any line left blank.
        cif = ctk.CTkFrame(top, fg_color="transparent")
        cif.grid(row=10, column=0, padx=16, pady=(0, 14), sticky="ew")
        cif.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkLabel(cif, text="YOUR CONTACT INFO (shown in Contact Footer section)",
                     text_color=T.TEXT_DIM, font=ctk.CTkFont(size=10, weight="bold")).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 4))

        for i, (lbl, var, ph) in enumerate([
            ("Business/Org Name", self._morg, "Your Company"),
            ("WhatsApp Number",   self._mwa,   "+1 555 0100"),
            ("Email",             self._memail, "you@example.com"),
            ("Address",           self._maddr,  "City, Country"),
        ]):
            ctk.CTkLabel(cif, text=lbl, text_color=T.TEXT_MUTED,
                         font=ctk.CTkFont(size=11)).grid(
                row=1 + (i // 2) * 2, column=i % 2, sticky="w", padx=2, pady=(4, 0))
            ctk.CTkEntry(cif, textvariable=var, placeholder_text=ph,
                         fg_color=T.BG_INNER, border_color=T.BG_BORDER,
                         text_color=T.TEXT_HEAD,
                         placeholder_text_color=T.TEXT_DIM,
                         font=ctk.CTkFont(size=11)).grid(
                row=2 + (i // 2) * 2, column=i % 2, sticky="ew", padx=2)
            var.trace_add("write", lambda *_: self._schedule_preview())

        # ── Middle: sections list ─────────────────────────────────────────────
        mid = ctk.CTkFrame(left, fg_color="transparent")
        mid.grid(row=1, column=0, sticky="nsew")
        mid.grid_columnconfigure(0, weight=1)
        mid.grid_rowconfigure(1, weight=1)

        # Add section toolbar
        tb = ctk.CTkFrame(mid, fg_color=T.BG_SURFACE, corner_radius=12,
                           border_width=1, border_color=T.BG_BORDER)
        tb.grid(row=0, column=0, sticky="ew", pady=(0,6))
        tb.grid_columnconfigure(0, weight=1)
        # Item 24 of the Live Testing Findings pass (Round 2), follow-up:
        # the AI box + presets + template gallery above are the primary,
        # easy path (confirmed working well in recent live testing) --
        # manual section management is the power-user path, and per the
        # user's own explicit choice this is now collapsed behind a real
        # toggle (not just relabeled), so it isn't visible by default.
        ctk.CTkLabel(tb, text="🔧  Advanced: Sections",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color=T.TEXT_HEAD).grid(
            row=0,column=0,padx=12,pady=8,sticky="w")

        self._sections_advanced_expanded = False
        # Item 27 (Final Premium Polish Pass): was fg_color="transparent" on
        # this T.BG_SURFACE toolbar -- ACCENT text measured 2.16:1 in Dark
        # mode, a real WCAG fail. Matches History's "Duplicate" button fix
        # (Item 12): T.BG_INNER gives 3.2:1 (accepted) and a real, distinct
        # hover_color.
        self._adv_toggle_btn = ctk.CTkButton(
            tb, text="▶  Show", width=76, height=26,
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color=T.BG_INNER, hover_color=T.BG_BORDER,
            border_width=1, border_color=T.ACCENT, text_color=T.ACCENT_TEXT,
            command=self._toggle_advanced_sections)
        self._adv_toggle_btn.grid(row=0, column=1, padx=12, pady=6, sticky="e")

        # Collapsible body: add-section buttons + the sections scroll list.
        # Not grid()'d here -- stays hidden (collapsed) until the toggle
        # above is clicked.
        self._sections_body = ctk.CTkFrame(mid, fg_color="transparent")
        self._sections_body.grid_columnconfigure(0, weight=1)
        self._sections_body.grid_rowconfigure(1, weight=1)

        sbf = ctk.CTkFrame(self._sections_body, fg_color=T.BG_SURFACE, corner_radius=12,
                            border_width=1, border_color=T.BG_BORDER)
        sbf.grid(row=0, column=0, sticky="ew", pady=(0,6))
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
            self._sections_body, fg_color=T.BG_MAIN, corner_radius=12)
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
                      text_color=T.TEXT_HEAD,
                      command=self._generate).grid(
            row=0, column=0, sticky="ew", pady=(0,6))

        r2 = ctk.CTkFrame(bot, fg_color="transparent")
        r2.grid(row=1, column=0, sticky="ew")
        r2.grid_columnconfigure((0,1,2), weight=1)
        ctk.CTkButton(r2, text="🌐 Open Browser",
                      fg_color=T.SUCCESS, hover_color=T.SUCCESS_HOVER,
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

        # Item 11.6 of the Live Testing Findings pass (Round 2): one-click
        # hand-off into the real Compose send pipelines, instead of the
        # card only ever being usable via this tab's own separate (and, for
        # WhatsApp, mocked -- see this file's own "current state" caveat)
        # bulk-send flow.
        ctk.CTkButton(bot, text="📩 Insert into Compose", height=34,
                      fg_color=T.BADGE_BG, hover_color=T.BG_BORDER,
                      text_color=T.ACCENT_TEXT, font=ctk.CTkFont(size=12, weight="bold"),
                      command=self._insert_into_compose).grid(
            row=3, column=0, sticky="ew", pady=(6, 0))

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
                         text_color=T.ACCENT_TEXT).pack(anchor="w",padx=8,pady=(0,8))

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

    def _insertion_index_for_new_section(self, stype: str) -> int:
        """Item 22 of the Live Testing Findings pass (Round 2): where a
        newly-added section of `stype` should land so the card reads
        coherently without manual reordering -- right after the last
        existing section whose own type is at or before `stype` in the
        canonical _SECTION_ORDER (e.g. adding "Price Box" after
        Header/Text/Contact already exist lands it between Text and
        Contact, not appended after Contact). Unrecognized types (there
        are none today, but defensively) sort last."""
        new_rank = _SECTION_ORDER.index(stype) if stype in _SECTION_ORDER else len(_SECTION_ORDER)
        for i, sec in enumerate(self._sections):
            existing_rank = (_SECTION_ORDER.index(sec["type"])
                              if sec["type"] in _SECTION_ORDER else len(_SECTION_ORDER))
            if existing_rank > new_rank:
                return i
        return len(self._sections)

    def _toggle_advanced_sections(self):
        """Item 24 follow-up: the manual section-builder is collapsed by
        default (a real hide, not just a visual de-emphasis) so a new user's
        first look at Cards is the AI box/presets/template gallery, not a
        wall of section-type buttons. Clicking the toggle reveals it."""
        self._sections_advanced_expanded = not self._sections_advanced_expanded
        if self._sections_advanced_expanded:
            self._sections_body.grid(row=1, column=0, sticky="nsew")
            self._adv_toggle_btn.configure(text="▼  Hide")
        else:
            self._sections_body.grid_remove()
            self._adv_toggle_btn.configure(text="▶  Show")

    def _add_section(self, stype: str):
        idx = len(self._sections)
        data: dict = {}
        visible_var = ctk.BooleanVar(value=True)

        card = ctk.CTkFrame(self._sections_scroll, fg_color=T.BG_SURFACE,
                             corner_radius=12, border_width=1, border_color=T.BG_BORDER)
        card.grid_columnconfigure(0, weight=1)

        label = next((lbl for lbl, t in SECTION_TYPES if t == stype), stype)
        section_num = idx + 1

        hdr = ctk.CTkFrame(card, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 4))
        hdr.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(hdr, text="↕", text_color=T.ACCENT_TEXT,
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
            fg_color=T.ACCENT, border_color=T.ACCENT,
            hover_color=T.ACCENT_HOVER, checkmark_color=T.TEXT_HEAD,
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

        if stype == "header":
            ctk.CTkLabel(
                body,
                text="Uses the App Name, Icon and Tagline from Card Identity above.\n"
                     "Hide or reorder this section to control whether/where the "
                     "branded header appears.",
                text_color=T.TEXT_MUTED, font=ctk.CTkFont(size=11),
                justify="left", wraplength=280,
            ).pack(anchor="w", pady=(2, 6))

        elif stype == "banner":
            v = ctk.StringVar()
            lbl("Image URL (paste any image link)")
            entry(v, "https://example.com/banner.jpg")
            v.trace_add("write", lambda *_: self._schedule_preview())
            data["_url_var"] = v
            data["_uploaded_uri"] = None

            upload_status = ctk.StringVar(value="")

            def _on_picked(uri: str, filename: str, data=data, status=upload_status) -> None:
                data["_uploaded_uri"] = uri
                status.set(f"✓ Using uploaded file: {filename}")
                self._schedule_preview()

            def _clear_upload(data=data, status=upload_status) -> None:
                data["_uploaded_uri"] = None
                status.set("")
                self._schedule_preview()

            upload_row = ctk.CTkFrame(body, fg_color="transparent")
            upload_row.pack(fill="x", pady=(0, 6))
            ctk.CTkButton(upload_row, text="📁 Upload from device", width=1,
                          fg_color=T.BADGE_BG, hover_color=T.BG_BORDER,
                          text_color=T.TEXT_HEAD, font=ctk.CTkFont(size=11),
                          command=lambda: self._pick_local_image(_on_picked)).pack(side="left")
            ctk.CTkButton(upload_row, text="✕", width=28,
                          fg_color=T.BADGE_BG, hover_color=T.DANGER_HOVER,
                          text_color=T.TEXT_HEAD, font=ctk.CTkFont(size=11),
                          command=_clear_upload).pack(side="left", padx=(4, 0))
            ctk.CTkLabel(upload_row, textvariable=upload_status,
                         text_color=T.SUCCESS, font=ctk.CTkFont(size=10)).pack(
                side="left", padx=(8, 0))
            data["_upload_status_var"] = upload_status

        elif stype == "youtube":
            v = ctk.StringVar()
            v.trace_add("write", lambda *_: self._schedule_preview())
            lbl("YouTube video link")
            entry(v, "https://youtube.com/watch?v=...")
            ctk.CTkLabel(body, text="▶ Video will play inside the card",
                         text_color=T.ACCENT_TEXT, font=ctk.CTkFont(size=11)).pack(anchor="w")
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
            ctk.CTkLabel(rr,text="Sale Price",text_color=T.TEXT_MUTED,
                         font=ctk.CTkFont(size=11)).grid(row=0,column=0,sticky="w",padx=2)
            ctk.CTkLabel(rr,text="Original Price",text_color=T.TEXT_MUTED,
                         font=ctk.CTkFont(size=11)).grid(row=0,column=1,sticky="w",padx=2)
            ctk.CTkEntry(rr,textvariable=pv,fg_color=T.BG_INNER,
                         border_color=T.BG_BORDER,text_color=T.TEXT_HEAD,
                         placeholder_text_color=T.TEXT_DIM).grid(row=1,column=0,sticky="ew",padx=2,pady=(2,4))
            ctk.CTkEntry(rr,textvariable=opv,fg_color=T.BG_INNER,
                         border_color=T.BG_BORDER,text_color=T.TEXT_HEAD,
                         placeholder_text_color=T.TEXT_DIM).grid(row=1,column=1,sticky="ew",padx=2,pady=(2,4))
            # Item 11.4: a live, auto-calculated discount % -- purely a
            # display aid in the editor (the actual badge in the exported
            # card is computed the same way, at collection time, by
            # _collect_sections via the shared compute_discount_percent
            # helper, so the editor and the real output can never disagree).
            discount_var = ctk.StringVar(value="")
            ctk.CTkLabel(rr, textvariable=discount_var, text_color=T.SUCCESS,
                         font=ctk.CTkFont(size=11, weight="bold")).grid(
                row=2, column=0, columnspan=2, sticky="w", padx=2, pady=(0, 6))

            def _update_discount_preview(*_a, pv=pv, opv=opv, discount_var=discount_var):
                pct = compute_discount_percent(pv.get(), opv.get())
                discount_var.set(f"🔥 {pct}% OFF — auto-calculated" if pct else "")

            pv.trace_add("write", _update_discount_preview)
            opv.trace_add("write", _update_discount_preview)
            _update_discount_preview()

            lbl("Price note")
            entry(nv,"e.g. One-time · Lifetime")

            # Item 11.5: the purchase button now lives directly on the Price
            # section -- "Button Text" (default "Buy Now") and "Purchase
            # Link URL" -- instead of requiring a separate Links section
            # with a specifically-labeled "buy" entry to make the button
            # actually clickable.
            btv = ctk.StringVar(value="Buy Now")
            buv = ctk.StringVar(value="")
            lbl("Button Text")
            entry(btv, "Buy Now")
            lbl("Purchase Link URL")
            entry(buv, "https://your-payment-link.com")

            for v in (pv, opv, nv, btv, buv):
                v.trace_add("write", lambda *_: self._schedule_preview())

            data["_price"]=pv; data["_old"]=opv; data["_note"]=nv
            data["_btn_text"]=btv; data["_buy_url"]=buv

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
                         text_color=T.ACCENT_TEXT,
                         font=ctk.CTkFont(size=11)).pack(anchor="w",pady=4)

        insert_at = self._insertion_index_for_new_section(stype)
        self._sections.insert(insert_at, sec_entry)
        # Re-grid every section at its (possibly shifted) row position --
        # same technique _move_section already uses for manual reordering.
        for row, sec in enumerate(self._sections):
            if sec["frame"].winfo_exists():
                sec["frame"].grid(row=row, column=0, sticky="ew", pady=(0, 6), padx=2)
        self._sec_row = len(self._sections)
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

            if stype == "header":
                pass   # uses meta (App Name/Icon/Tagline), same as "contact"
            elif stype == "banner":
                uploaded = data.get("_uploaded_uri")
                d["url"] = uploaded or data.get("_url_var", ctk.StringVar()).get()
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
                d["button_text"] = data.get("_btn_text", ctk.StringVar()).get().strip()
                d["buy_url"]     = _clean_url(data.get("_buy_url", ctk.StringVar()).get())
                d["discount_percent"] = compute_discount_percent(d["price"], d["old_price"])
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
        """Apply a built-in visual card template, or reveal the custom
        background controls if "Custom" was picked (see __init__'s
        _custom_style comment for why that's a separate dict, not an entry
        added to CARD_STYLE_TEMPLATES)."""
        self._style_name = name
        if name == "Custom":
            self._custom_bg_row.grid()
        else:
            self._custom_bg_row.grid_remove()
            style = CARD_STYLE_TEMPLATES.get(name, CARD_STYLE_TEMPLATES["Dark Premium"])
            self._accent = style.get("accent", self._accent)
        if hasattr(self, "_accent_swatch_canvases"):
            self._redraw_accent_swatches()
        self._schedule_preview()

    def _pick_custom_bg_color(self) -> None:
        current = self._custom_style.get("bg", "#1a1a2e")
        picked = colorchooser.askcolor(title="Pick background color", color=current)
        if not picked or not picked[1]:
            return
        color = picked[1]
        text_color = _contrast_text_color(color)
        self._custom_style.update({
            "bg": color, "body_bg": color, "header_bg": color, "text": text_color,
        })
        self._custom_bg_status.set(f"✓ Solid color {color}")
        self._redraw_template_gallery()
        self._schedule_preview()

    def _pick_custom_bg_image(self) -> None:
        def _on_picked(uri: str, filename: str) -> None:
            bg_value = f"url({uri}) center center / cover no-repeat"
            # Item 23 of the Live Testing Findings pass (Round 2): this
            # previously set BOTH "bg" (the actual .card panel background,
            # the real visible card) AND "body_bg" (the full-page backdrop,
            # only ever visible as a thin margin around the card) to the
            # exact same image url(...) value -- embedding the same,
            # potentially multi-hundred-KB base64-inflated image payload
            # TWICE in the final HTML for essentially zero visual benefit.
            # Confirmed directly with a diagnostic: a 50KB fake image
            # payload appeared 2x in a real generate_html() render. Now
            # only .card gets the image; body_bg falls back to this same
            # plain neutral the feature already uses as its own default/
            # cleared state, instead of a second copy of the image.
            self._custom_style.update({"bg": bg_value, "body_bg": "#1a1a2e"})
            self._custom_bg_status.set(f"✓ Using image: {filename}")
            self._redraw_template_gallery()
            self._schedule_preview()
        self._pick_local_image(_on_picked)

    def _clear_custom_bg_image(self) -> None:
        color = "#1a1a2e"
        self._custom_style.update({
            "bg": color, "body_bg": color, "header_bg": color,
            "text": "rgba(255,255,255,0.85)",
        })
        self._custom_bg_status.set("")
        self._redraw_template_gallery()
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
        if self._style_name == "Custom":
            style = self._custom_style
        else:
            style = CARD_STYLE_TEMPLATES.get(self._style_name, CARD_STYLE_TEMPLATES["Dark Premium"])
        return {
            "app_name":   self._mname.get().strip(),
            "icon":       self._micon.get().strip() or "⭐",
            "icon_image": self._micon_image_uri or "",
            "tagline":    self._mtag.get().strip(),
            "accent":     self._accent,
            "org":        self._morg.get().strip(),
            "wa":         self._mwa.get().strip(),
            "email":      self._memail.get().strip(),
            "addr":       self._maddr.get().strip(),
            "style":      style,
            "buy_link":   self._collect_buy_link(),
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
        """Debounced live preview update (500 ms). Also the single, shared
        place every content-changing action already routes through, so it
        doubles as the "content is dirty" tracker for Item 17's preset-
        switch confirmation."""
        self._card_dirty = True
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

    # ─── Item 11.6: one-click Insert into Compose ─────────────────────────────

    def _build_whatsapp_card_text(self, meta: dict) -> str:
        """WhatsApp can't render HTML, so the card's key selling points
        (headline, description, price/discount, and the real purchase
        link) are flattened into a real plain-text message instead of a
        static image or a broken embed."""
        lines = [meta["app_name"] + (f" — {meta['tagline']}" if meta.get("tagline") else "")]

        desc_box = next(
            (s["data"].get("_text_box") for s in self._sections if s["type"] == "text"), None)
        description = desc_box.get("1.0", "end").strip() if desc_box else ""
        if description:
            lines.append("")
            lines.append(description)

        price_sec = next((s for s in self._sections if s["type"] == "price"), None)
        if price_sec:
            price = price_sec["data"].get("_price", ctk.StringVar()).get().strip()
            old_price = price_sec["data"].get("_old", ctk.StringVar()).get().strip()
            if price:
                pct = compute_discount_percent(price, old_price)
                price_line = f"💰 {price}"
                if old_price:
                    price_line += f" (was {old_price})"
                if pct:
                    price_line += f" — {pct}% OFF"
                lines.append("")
                lines.append(price_line)
            btn_text = price_sec["data"].get("_btn_text", ctk.StringVar()).get().strip() or "Buy Now"
            buy_url = (_clean_url(price_sec["data"].get("_buy_url", ctk.StringVar()).get())
                       or self._collect_buy_link())
            if buy_url:
                lines.append(f"👉 {btn_text}: {buy_url}")

        return "\n".join(lines).strip()

    def _insert_into_compose(self) -> None:
        """One-click hand-off into the real Compose send pipelines (Item
        11.6): the full HTML card for Email (via Item 10's rich-text
        importer, so it lands as genuine editable/sendable content, not
        raw markup), or a real plain-text summary + purchase link for
        WhatsApp (which has no HTML rendering capability at all)."""
        if self.main_window is None:
            messagebox.showwarning(
                "Unavailable", "Insert into Compose requires the main app window.")
            return

        self._html = self._get_export_html()
        meta = self._collect_meta()
        mw = self.main_window
        channel = mw._compose_channel_var.get()

        mw._show_view("Compose")
        if channel == "Email":
            mw._compose_em_body.delete("1.0", "end")
            mw._load_html_into_email_editor(self._html)
            subject = (f"{meta['app_name']} — {meta['tagline']}"
                       if meta.get("tagline") else meta["app_name"])
            mw._em_subj_var.set(subject)
            mw._update_email_warnings()
        else:
            mw.message_textbox.delete("1.0", "end")
            mw.message_textbox.insert("1.0", self._build_whatsapp_card_text(meta))
            mw._on_wa_message_changed()

        show_toast(mw, "Card inserted into Compose.", kind="success")
        self._status.set("✅ Inserted into Compose.")

    # ─── Bulk Send dialog ─────────────────────────────────────────────────────

    def _show_bulk_send(self):
        if not self._html:
            self._generate()

        if self.main_window is None:
            messagebox.showerror("Unavailable", "Bulk send requires the main app window.")
            return

        dlg = ctk.CTkToplevel(self)
        dlg.title("Bulk Send Card")
        # Centered on the real top-level window (self.main_window), not on
        # `self` -- `self` is an embedded CTkFrame inside the main window,
        # not a Toplevel, so its winfo_x()/winfo_y() are relative to its own
        # parent container rather than the screen; centering against it
        # would compute a wrong, tiny-offset position.
        center_on_parent(dlg, 560, 780, self.main_window)
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
                           text_color=T.TEXT_MUTED,
                           fg_color=T.ACCENT, border_color=T.ACCENT,
                           hover_color=T.ACCENT_HOVER).grid(
            row=1,column=0,padx=14,pady=(0,8),sticky="w")
        ctk.CTkRadioButton(ch,text="📧 Email (HTML card)",
                           variable=channel_var,value="email",
                           text_color=T.TEXT_MUTED,
                           fg_color=T.ACCENT, border_color=T.ACCENT,
                           hover_color=T.ACCENT_HOVER).grid(
            row=1,column=1,padx=14,pady=(0,8),sticky="w")

        consent_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(ch, text="I have consent from these contacts to message them",
                         variable=consent_var, text_color=T.TEXT_MUTED,
                         font=ctk.CTkFont(size=11),
                         fg_color=T.ACCENT, border_color=T.ACCENT,
                         hover_color=T.ACCENT_HOVER, checkmark_color=T.TEXT_HEAD).grid(
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
                        card_summary, contact_dicts, api_key, channel,
                        provider=self.main_window._ai_provider.get())
                except AIServiceError as ex:
                    # Computed here, not inside the deferred lambda -- `ex` is
                    # auto-deleted by Python at except-block exit, before
                    # dlg.after()'s callback ever runs, which raised a NameError
                    # Tk's default handler silently swallowed (stderr only).
                    error_message = str(ex)
                    dlg.after(0, lambda: _ai_failed(error_message))
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
            # This bulk-send flow imports contacts directly from a file
            # (bypassing the DB), so opted_out never gets set on these
            # in-memory Contact objects — cross-check against the real,
            # DB-backed contact list by phone/email so someone who already
            # unsubscribed via the main app can never be re-contacted here.
            opted_out_phones = {c.phone for c in self.main_window.contacts if c.opted_out and c.phone}
            opted_out_emails = {c.email.lower() for c in self.main_window.contacts if c.opted_out and c.email}
            before_count = len(sendable)
            sendable = [c for c in sendable
                        if c.phone not in opted_out_phones
                        and (c.email or "").lower() not in opted_out_emails]
            skipped_opt_out = before_count - len(sendable)
            if skipped_opt_out:
                logger.info(f"AI Cards bulk send: skipped {skipped_opt_out} opted-out contact(s)")
            if not sendable:
                messagebox.showwarning("No Messages",
                    "All matching contacts have opted out.", parent=dlg)
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
                        error_message = str(ex)  # see generate_personalization's worker for why
                        dlg.after(0, lambda: messagebox.showerror(
                            "Send failed", error_message, parent=dlg))
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
                        error_message = str(ex)  # see generate_personalization's worker for why
                        dlg.after(0, lambda: messagebox.showerror(
                            "Send failed", error_message, parent=dlg))

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
                                  fg_color=T.SUCCESS,hover_color=T.SUCCESS_HOVER,
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

    def _select_accent(self, h: str) -> None:
        """Real replacement for the old _set_accent -- also redraws the
        swatch selection ring and refreshes the live preview, neither of
        which the old version did (a real, pre-existing gap: picking an
        accent color previously never triggered a preview refresh at all)."""
        self._accent = h
        self._redraw_accent_swatches()
        self._schedule_preview()

    def _redraw_accent_swatches(self) -> None:
        for color, canvas in getattr(self, "_accent_swatch_canvases", {}).items():
            if not canvas.winfo_exists():
                continue
            canvas.delete("all")
            canvas.create_rectangle(2, 2, 28, 28, fill=color, outline="")
            is_selected = color.lower() == self._accent.lower()
            border_color = T.resolve(T.TEXT_HEAD) if is_selected else T.resolve(T.BG_BORDER)
            canvas.create_rectangle(1, 1, 29, 29, outline=border_color,
                                     width=3 if is_selected else 1)

    def _custom_color(self):
        c = colorchooser.askcolor(title="Pick color", color=self._accent)
        if c and c[1]:
            self._select_accent(c[1])

    def _select_template(self, name: str) -> None:
        self._template_var.set(name)
        self._apply_card_template(name)

    def _redraw_template_gallery(self) -> None:
        selected = self._template_var.get()
        for name, canvas in getattr(self, "_template_thumb_canvases", {}).items():
            if not canvas.winfo_exists():
                continue
            canvas.delete("all")
            style = self._custom_style if name == "Custom" else CARD_STYLE_TEMPLATES.get(
                name, CARD_STYLE_TEMPLATES["Dark Premium"])
            header_color = _hex_or_fallback(style.get("header_bg"), "#1a1a2e")
            body_color = _hex_or_fallback(style.get("body_bg"), "#111827")
            accent_color = _hex_or_fallback(style.get("accent"), "#6c63ff")
            text_color = _hex_or_fallback(style.get("text"), "#ffffff")
            width, height = 88, 54
            canvas.create_rectangle(0, 0, width, height, fill=body_color, outline="")
            canvas.create_rectangle(0, 0, width, 14, fill=header_color, outline="")
            canvas.create_oval(6, 20, 18, 32, fill=accent_color, outline="")
            canvas.create_rectangle(24, 22, 70, 26, fill=accent_color, outline="")
            canvas.create_rectangle(24, 30, 60, 33, fill=text_color, outline="")
            is_selected = name == selected
            border_color = T.resolve(T.ACCENT) if is_selected else T.resolve(T.BG_BORDER)
            canvas.create_rectangle(1, 1, width - 1, height - 1, outline=border_color,
                                     width=3 if is_selected else 1)
        for name, label_widget in getattr(self, "_template_thumb_labels", {}).items():
            if label_widget.winfo_exists():
                label_widget.configure(
                    text_color=T.ACCENT_TEXT if name == selected else T.TEXT_MUTED)

    # ─── Item 11.1: drag-and-drop logo/icon upload + live preview + crop ──────

    # A real drop zone, not a 44x44 icon -- Item 20 of the Live Testing
    # Findings pass (Round 2). Big enough to hold "📁 / Drag & drop logo
    # here, / or click to browse" comfortably in the empty state, and to
    # show a genuinely readable thumbnail once an image is uploaded.
    _ICON_ZONE_WIDTH = 128
    _ICON_ZONE_HEIGHT = 100

    def _build_icon_drop_zone(self, parent) -> None:
        """Replaces the plain emoji text field with a real drop target
        (drag-and-drop via tkinterdnd2, the same registration pattern
        contact_import_review.py already uses -- TkinterDnD._require() is
        already called once on the app root in main_window.py, so no extra
        setup is needed here) plus a live thumbnail preview and a Crop
        button. The emoji entry stays underneath as the fallback path for
        anyone who doesn't want to upload an image at all.

        Item 20 of the Live Testing Findings pass (Round 2): the original
        version of this zone was a plain 44x44 canvas with no visual
        indication it was a drop target at all (just a tiny emoji, "small,
        plain, sketch-like" per the report) -- now a real dashed-border
        drop zone with explicit "Drag & drop logo here, or click to
        browse" helper text (matching the pattern Contacts' own CSV import
        drop zone already established: an icon, helper text, and a click
        affordance), a properly-sized thumbnail once filled instead of a
        tiny icon, and real hover feedback (border + background both shift
        on <Enter>/<Leave> -- a plain tk.Canvas has no CSS hover pseudo-
        class, so this is hand-rolled the same way _draw_nav_accent already
        hand-paints its own canvas elsewhere in this app)."""
        zone_wrap = ctk.CTkFrame(parent, fg_color="transparent")
        zone_wrap.grid(row=1, column=1, padx=2)

        self._icon_preview_canvas = tk.Canvas(
            zone_wrap, width=self._ICON_ZONE_WIDTH, height=self._ICON_ZONE_HEIGHT,
            highlightthickness=0, bg=T.resolve(T.BG_INNER), cursor="hand2")
        self._icon_preview_canvas.pack(pady=(0, 4))
        self._icon_preview_canvas.bind("<Button-1>", lambda _e: self._browse_icon_image())
        self._icon_zone_hovering = False
        self._icon_preview_canvas.bind("<Enter>", lambda _e: self._set_icon_zone_hover(True))
        self._icon_preview_canvas.bind("<Leave>", lambda _e: self._set_icon_zone_hover(False))
        self._icon_photo_ref = None  # keeps the PhotoImage alive -- Tk drops it otherwise

        if HAS_DND:
            try:
                self._icon_preview_canvas.drop_target_register(DND_FILES)
                self._icon_preview_canvas.dnd_bind("<<Drop>>", self._on_icon_drop)
            except Exception:
                pass  # DnD registration can fail on some platforms -- click-to-browse still works

        btn_row = ctk.CTkFrame(zone_wrap, fg_color="transparent")
        btn_row.pack()
        self._icon_crop_btn = ctk.CTkButton(
            btn_row, text="✂ Crop", width=60, height=22, corner_radius=5,
            fg_color=T.BADGE_BG, hover_color=T.BG_BORDER, text_color=T.TEXT_HEAD,
            font=ctk.CTkFont(size=10), state="disabled",
            command=self._open_icon_crop_dialog)
        self._icon_crop_btn.pack(side="left", padx=(0, 2))
        ctk.CTkButton(
            btn_row, text="✕ Remove", width=68, height=22, corner_radius=5,
            fg_color=T.BADGE_BG, hover_color=T.DANGER_HOVER, text_color=T.TEXT_HEAD,
            font=ctk.CTkFont(size=10), command=self._clear_icon_image).pack(side="left")

        emoji_row = ctk.CTkFrame(zone_wrap, fg_color="transparent")
        emoji_row.pack(pady=(4, 0))
        ctk.CTkLabel(emoji_row, text="or emoji:", text_color=T.TEXT_DIM,
                     font=ctk.CTkFont(size=10)).pack(side="left", padx=(0, 4))
        ctk.CTkEntry(emoji_row, textvariable=self._micon, placeholder_text="⭐",
                     width=44, justify="center",
                     fg_color=T.BG_INNER, border_color=T.BG_BORDER,
                     text_color=T.TEXT_HEAD, placeholder_text_color=T.TEXT_DIM,
                     font=ctk.CTkFont(size=11)).pack(side="left")
        self._micon.trace_add(
            "write", lambda *_: (self._redraw_icon_preview(), self._schedule_preview()))

        self._redraw_icon_preview()

    def _set_icon_zone_hover(self, hovering: bool) -> None:
        self._icon_zone_hovering = hovering
        self._redraw_icon_preview()

    def _redraw_icon_preview(self) -> None:
        """Live preview (Item 11.1, redesigned per Item 20): shows the
        uploaded/cropped logo as a real, properly-sized thumbnail filling
        most of the zone, or -- when empty -- a dashed-border drop zone
        with explicit drag-and-drop helper text, not a tiny icon. Border/
        background both shift on hover as the only available stand-in for
        a CSS :hover state on a plain Canvas."""
        canvas = getattr(self, "_icon_preview_canvas", None)
        if canvas is None or not canvas.winfo_exists():
            return
        canvas.delete("all")
        width, height = self._ICON_ZONE_WIDTH, self._ICON_ZONE_HEIGHT
        hovering = getattr(self, "_icon_zone_hovering", False)
        canvas.configure(bg=T.resolve(T.BADGE_BG if hovering else T.BG_INNER))
        border_color = T.resolve(T.ACCENT) if hovering else T.resolve(T.BG_BORDER)

        if self._micon_image_uri:
            try:
                img = decode_data_uri_to_image(self._micon_image_uri)
                img.thumbnail((width - 12, height - 12))
                photo = ImageTk.PhotoImage(img)
                self._icon_photo_ref = photo
                canvas.create_image(width // 2, height // 2, image=photo)
                canvas.create_rectangle(1, 1, width - 1, height - 1,
                                         outline=border_color, width=2)
                return
            except Exception:
                logger.warning("Icon preview decode failed", exc_info=True)

        canvas.create_rectangle(3, 3, width - 3, height - 3,
                                 outline=border_color, width=2, dash=(5, 3))
        # Item 25: a canvas text item with no `width=` never wraps, even
        # with manual "\n" breaks -- "Drag & drop logo here," alone measures
        # ~142px, wider than this 128px zone, so half of it rendered at a
        # negative x-coordinate and was clipped by the canvas viewport
        # (confirmed by direct measurement before fixing, not guessed) --
        # exactly the reported "cut off on the left" symptom. `width=`
        # forces real word-wrap regardless of theme/font-metrics variance.
        canvas.create_text(
            width // 2, height // 2,
            text="📁\nDrag & drop logo here,\nor click to browse",
            fill=T.resolve(T.TEXT_MUTED), font=("Segoe UI", 10), justify="center",
            width=width - 16)

    def _browse_icon_image(self) -> None:
        path = filedialog.askopenfilename(
            title="Choose a logo/icon image",
            filetypes=[("Image files", "*.png *.jpg *.jpeg *.gif *.webp"),
                       ("All files", "*.*")])
        if path:
            self._load_icon_image_path(path)

    def _on_icon_drop(self, event) -> None:
        raw = event.data.strip()
        if raw.startswith("{") and raw.endswith("}"):
            raw = raw[1:-1]
        path = raw.split("} {")[0] if "} {" in raw else raw
        if path:
            self._load_icon_image_path(path)

    def _load_icon_image_path(self, path: str) -> None:
        try:
            uri = image_file_to_data_uri(path)
        except ImageUploadError as exc:
            if self.main_window is not None:
                show_toast(self.main_window, str(exc), kind="error")
            else:
                messagebox.showwarning("Image not used", str(exc))
            return
        self._micon_image_uri = uri
        self._icon_crop_btn.configure(state="normal")
        self._redraw_icon_preview()
        self._schedule_preview()

    def _clear_icon_image(self) -> None:
        self._micon_image_uri = None
        if hasattr(self, "_icon_crop_btn"):
            self._icon_crop_btn.configure(state="disabled")
        self._redraw_icon_preview()
        self._schedule_preview()

    def _open_icon_crop_dialog(self) -> None:
        """A simple, scoped square-crop dialog: the source image is scaled
        to fit a 300x300 canvas, a fixed-size square selection box can be
        dragged (not resized -- a deliberately scoped "simple" crop, not a
        full photo editor) to choose the crop region, then Apply Crop
        re-crops the ORIGINAL full-resolution image (not the on-screen
        scaled-down preview) via crop_and_encode_image."""
        if not self._micon_image_uri:
            return
        try:
            source_img = decode_data_uri_to_image(self._micon_image_uri)
        except Exception:
            messagebox.showerror("Crop", "Could not open this image for cropping.")
            return

        dlg = ctk.CTkToplevel(self)
        dlg.title("Crop Logo")
        parent_for_center = self.main_window if self.main_window is not None else self
        center_on_parent(dlg, 380, 460, parent_for_center)
        dlg.grab_set()
        dlg.configure(fg_color=T.BG_MAIN)
        dlg.bind("<Escape>", lambda _e: dlg.destroy())

        ctk.CTkLabel(dlg, text="Drag the box to choose the crop area",
                     text_color=T.TEXT_MUTED, font=ctk.CTkFont(size=11)).pack(pady=(16, 6))

        canvas_size = 300
        canvas = tk.Canvas(dlg, width=canvas_size, height=canvas_size,
                            highlightthickness=1, highlightbackground=T.resolve(T.BG_BORDER),
                            bg=T.resolve(T.BG_INNER))
        canvas.pack(padx=16)

        src_w, src_h = source_img.size
        scale = min(canvas_size / src_w, canvas_size / src_h)
        disp_w, disp_h = max(1, int(src_w * scale)), max(1, int(src_h * scale))
        display_img = source_img.resize((disp_w, disp_h))
        photo = ImageTk.PhotoImage(display_img)
        offset_x, offset_y = (canvas_size - disp_w) // 2, (canvas_size - disp_h) // 2
        canvas.create_image(offset_x, offset_y, anchor="nw", image=photo)
        canvas.image_ref = photo  # keep alive -- Tk drops unreferenced PhotoImages

        box_size = min(disp_w, disp_h)
        box = {"x": offset_x + (disp_w - box_size) / 2, "y": offset_y + (disp_h - box_size) / 2}
        rect_id = canvas.create_rectangle(
            box["x"], box["y"], box["x"] + box_size, box["y"] + box_size,
            outline=T.resolve(T.ACCENT), width=2)

        def clamp(value, lo, hi):
            return max(lo, min(value, hi))

        drag_state = {"active": False, "last_x": 0, "last_y": 0}

        def on_press(event):
            drag_state["active"] = True
            drag_state["last_x"], drag_state["last_y"] = event.x, event.y

        def on_drag(event):
            if not drag_state["active"]:
                return
            dx, dy = event.x - drag_state["last_x"], event.y - drag_state["last_y"]
            new_x = clamp(box["x"] + dx, offset_x, offset_x + disp_w - box_size)
            new_y = clamp(box["y"] + dy, offset_y, offset_y + disp_h - box_size)
            canvas.move(rect_id, new_x - box["x"], new_y - box["y"])
            box["x"], box["y"] = new_x, new_y
            drag_state["last_x"], drag_state["last_y"] = event.x, event.y

        def on_release(_event):
            drag_state["active"] = False

        canvas.bind("<Button-1>", on_press)
        canvas.bind("<B1-Motion>", on_drag)
        canvas.bind("<ButtonRelease-1>", on_release)

        def apply_crop():
            crop_x0 = (box["x"] - offset_x) / scale
            crop_y0 = (box["y"] - offset_y) / scale
            crop_side = box_size / scale
            crop_box = (
                int(crop_x0), int(crop_y0),
                int(crop_x0 + crop_side), int(crop_y0 + crop_side),
            )
            self._micon_image_uri = crop_and_encode_image(source_img, crop_box)
            self._redraw_icon_preview()
            self._schedule_preview()
            dlg.destroy()

        btn_row = ctk.CTkFrame(dlg, fg_color="transparent")
        btn_row.pack(pady=16)
        ctk.CTkButton(btn_row, text="Cancel", fg_color=T.BADGE_BG, hover_color=T.BG_BORDER,
                      text_color=T.TEXT_HEAD, command=dlg.destroy).pack(side="left", padx=(0, 10))
        ctk.CTkButton(btn_row, text="Apply Crop", fg_color=T.ACCENT, hover_color=T.ACCENT_HOVER,
                      text_color=T.TEXT_HEAD, font=ctk.CTkFont(weight="bold"),
                      command=apply_crop).pack(side="left")

    def _pick_local_image(self, on_picked) -> None:
        """Shared local-image-upload flow for both the banner section and
        the custom background (task #6) — opens a real file picker, encodes
        the chosen file as a data: URI (see image_file_to_data_uri), and
        hands the result to on_picked(data_uri, filename). Errors (file too
        large, not a real image, etc.) are shown as a toast, never raised
        as a raw traceback into the UI."""
        path = filedialog.askopenfilename(
            title="Choose an image",
            filetypes=[("Image files", "*.png *.jpg *.jpeg *.gif *.webp"),
                       ("All files", "*.*")],
        )
        if not path:
            return
        try:
            data_uri = image_file_to_data_uri(path)
        except ImageUploadError as exc:
            if self.main_window is not None:
                show_toast(self.main_window, str(exc), kind="error")
            else:
                messagebox.showwarning("Image not used", str(exc))
            return
        on_picked(data_uri, Path(path).name)

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
                    description, api_key, list(CARD_STYLE_TEMPLATES.keys()),
                    provider=self.main_window._ai_provider.get())
            except AIServiceError as ex:
                error_message = str(ex)  # see generate_personalization's worker for why
                self.after(0, lambda: self._on_ai_generate_failed(error_message))
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
        # Add sensible defaults -- header first, matching where it always
        # rendered before it became a real removable/reorderable section.
        self._add_section("header")
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
        # See _card_dirty's own comment in __init__: reset here, after this
        # method's own section-building calls already marked it dirty via
        # _schedule_preview, so a fresh load always starts clean.
        self._card_dirty = False

    def _confirm_and_load_preset(self, name: str) -> None:
        """Item 17 of the Live Testing Findings pass (Round 2): clicking a
        preset used to silently call _load_preset directly, discarding any
        existing AI-generated/edited card content with no warning at all.
        Now asks first whenever there's real content that would be lost --
        skipped when the card is already clean (e.g. right after a fresh
        preset load, or at first launch) so this doesn't nag on every
        click, only when it would actually cost the user something."""
        if not self._card_dirty:
            self._load_preset(name)
            return
        if not messagebox.askyesno(
            "Discard current card?",
            f"Switching to \"{name}\" will discard your current card content "
            "(including any AI-generated or edited text, prices, links, and "
            "images) and replace it with that preset's defaults.\n\n"
            "This can't be undone. Continue?",
        ):
            return
        self._load_preset(name)


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
    # Real bug found while studying this file for Item 11 of the Live
    # Testing Findings pass: _sync_widget_theme's own theme-toggle handler
    # (main_window.py) already reads getattr(self, "card_creator_tab", None)
    # to re-color the Cards preview host's raw tk.Frame background on every
    # Dark/Light/Warm Ivory switch -- but this attribute was never actually
    # assigned anywhere, so that whole block was silently always a no-op.
    main_window.card_creator_tab = tab