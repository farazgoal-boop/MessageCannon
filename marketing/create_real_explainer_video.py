from __future__ import annotations

import ctypes
import math
import re
import subprocess
import sys
import threading
import time
import textwrap
from pathlib import Path
from typing import Callable

import imageio.v2 as imageio
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageGrab

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.ui.main_window import MainWindow
from src.utils.license_manager import LicenseManager

OUTPUT_PATH = ROOT / "marketing" / "messagecannon-operational-walkthrough.mp4"
RAW_OUTPUT_PATH = ROOT / "marketing" / "messagecannon-operational-walkthrough-silent.mp4"
SAMPLE_CONTACTS = ROOT / "tests" / "sample_contacts.csv"
APP_ICON_PATH = ROOT / "src" / "assets" / "icons" / "app.png"
DEFAULT_DURATION_SECONDS = 104.0
FPS = 16
WINDOW_GEOMETRY = "1366x820+60+60"
FRAME_SIZE = (1280, 720)
START_DELAY_MS = 2200
CLICK_FLASH_SECONDS = 0.45
CURSOR_MOVE_SECONDS = 0.32
FRAME_HOLD_WINDOWS: list[tuple[float, float]] = []
AUDIO_INPUT_CANDIDATES = [
    ROOT / "marketing" / "messagecannon.m4a",
    ROOT / "marketing" / "marketingmessagecannon.m4a",
]


class RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long), ("right", ctypes.c_long), ("bottom", ctypes.c_long)]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", ctypes.c_uint32),
        ("biWidth", ctypes.c_long),
        ("biHeight", ctypes.c_long),
        ("biPlanes", ctypes.c_ushort),
        ("biBitCount", ctypes.c_ushort),
        ("biCompression", ctypes.c_uint32),
        ("biSizeImage", ctypes.c_uint32),
        ("biXPelsPerMeter", ctypes.c_long),
        ("biYPelsPerMeter", ctypes.c_long),
        ("biClrUsed", ctypes.c_uint32),
        ("biClrImportant", ctypes.c_uint32),
    ]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", ctypes.c_uint32 * 3)]


def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default()


FONT_TITLE = load_font(28, bold=True)
FONT_BODY = load_font(22, bold=True)
FONT_BODY_MEDIUM = load_font(20, bold=True)
FONT_BODY_SMALL = load_font(18, bold=True)
FONT_BODY_XSMALL = load_font(16, bold=True)
FONT_SMALL = load_font(16, bold=False)
FONT_META = load_font(18, bold=True)
FONT_PHONE = load_font(20, bold=True)
FONT_BRAND_CAPTION = load_font(14, bold=False)
FONT_CODE = load_font(15, bold=False)
FONT_CODE_TITLE = load_font(18, bold=True)
FONT_HERO = load_font(42, bold=True)
FONT_HERO_SUB = load_font(22, bold=False)
FONT_OUTRO = load_font(30, bold=True)

PYTHON_KEYWORDS = {
    "False",
    "None",
    "True",
    "and",
    "as",
    "class",
    "def",
    "elif",
    "else",
    "for",
    "from",
    "if",
    "import",
    "in",
    "is",
    "not",
    "or",
    "return",
    "try",
    "while",
    "with",
}


def load_app_icon(size: tuple[int, int] = (34, 34)) -> Image.Image | None:
    if not APP_ICON_PATH.exists():
        return None
    try:
        return Image.open(APP_ICON_PATH).convert("RGBA").resize(size, Image.Resampling.LANCZOS)
    except OSError:
        return None


APP_ICON = load_app_icon()


def resolve_audio_input() -> Path | None:
    for candidate in AUDIO_INPUT_CANDIDATES:
        if candidate.exists():
            return candidate
    return None


def detect_audio_duration_seconds(audio_path: Path | None) -> float:
    if audio_path is None:
        return DEFAULT_DURATION_SECONDS
    try:
        import imageio_ffmpeg

        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        result = subprocess.run(
            [ffmpeg_exe, "-i", str(audio_path)],
            capture_output=True,
            text=True,
            check=False,
        )
        output = f"{result.stdout}\n{result.stderr}"
        match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", output)
        if match:
            hours = int(match.group(1))
            minutes = int(match.group(2))
            seconds = float(match.group(3))
            total_seconds = (hours * 3600) + (minutes * 60) + seconds
            return max(60.0, math.ceil(total_seconds * 10) / 10)
    except Exception:
        pass
    return DEFAULT_DURATION_SECONDS


AUDIO_INPUT_PATH = resolve_audio_input()
DURATION_SECONDS = detect_audio_duration_seconds(AUDIO_INPUT_PATH)

BACKEND_CODE_WINDOWS: list[tuple[float, float, str, str, list[str]]] = [
    (
        64.0,
        74.0,
        "Python Backend",
        "src/session_manager.py",
        [
            "class SessionManager:",
            "    SESSION_TTL_HOURS = 48",
            "",
            "    def get_session_state(self) -> SessionState:",
            "        state = self._read_state()",
            "        expires_at = self._parse_dt(state.get(\"expires_at\", \"\"))",
            "        profile_exists = self._session_profile_exists()",
            "        if not profile_exists or expires_at is None:",
            "            return SessionState(False, None, True, \"Session expired - please scan QR\")",
            "        return SessionState(True, expires_at, False, \"Active session available\")",
        ],
    ),
    (
        74.0,
        86.0,
        "Delivery Tracking",
        "src/delivery_tracker.py",
        [
            "class DeliveryTracker:",
            "    POLLABLE_STATUSES = {\"sent\", \"delivered\"}",
            "",
            "    def create_message(self, phone: str, message_text: str, status: str = \"pending\") -> Optional[int]:",
            "        sent_at = datetime.now() if status in {\"sent\", \"delivered\", \"read\"} else None",
            "        delivered_at = datetime.now() if status in {\"delivered\", \"read\"} else None",
            "        return self.db.create_tracked_message(phone=phone, message_text=message_text, status=status)",
            "",
            "    def start_monitoring(self, status_resolver, interval_seconds: int = 5) -> None:",
            "        self._monitor_thread = threading.Thread(target=worker, daemon=True)",
        ],
    ),
    (
        86.0,
        96.0,
        "Automation Flow",
        "src/core/whatsapp_sender.py",
        [
            "def send_messages(self, contacts, messages, delay=30, use_jitter=True, max_messages=MAX_MESSAGES_PER_SESSION):",
            "    state = self.initialize()",
            "    if state.requires_qr and not state.is_active:",
            "        return {\"sent\": 0, \"failed\": capped_total, \"status\": state.status_text}",
            "    for index, (contact, message) in enumerate(zip(contacts[:capped_total], messages[:capped_total]), start=1):",
            "        tracked_id = self.delivery_tracker.create_message(contact.phone, message, status=\"pending\")",
            "        success = self._send_single_message(contact, message, tracked_id, event_callback)",
            "        if index < capped_total:",
            "            time.sleep(self._calculate_delay(delay, use_jitter))",
        ],
    ),
]


def patch_demo_mode() -> None:
    LicenseManager.check_license = staticmethod(
        lambda: {
            "status": "licensed",
            "days_remaining": None,
            "is_trial": False,
            "is_valid": True,
        }
    )

    def demo_bootstrap(self: MainWindow) -> None:
        self._set_session_status("Persistent session active and ready")
        self._log_activity("Demo mode session restored")

    def demo_periodic(self: MainWindow) -> None:
        return None

    MainWindow._start_session_bootstrap = demo_bootstrap
    MainWindow._periodic_refresh = demo_periodic


def get_window_rect(hwnd: int) -> tuple[int, int, int, int]:
    user32 = ctypes.windll.user32
    rect = RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    return rect.left, rect.top, rect.right, rect.bottom


def focus_window(hwnd: int) -> None:
    user32 = ctypes.windll.user32
    user32.ShowWindow(hwnd, 9)
    user32.SetForegroundWindow(hwnd)


def capture_window_frame(hwnd: int) -> Image.Image:
    left, top, right, bottom = get_window_rect(hwnd)
    width = max(1, right - left)
    height = max(1, bottom - top)
    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32
    window_dc = user32.GetWindowDC(hwnd)
    memory_dc = gdi32.CreateCompatibleDC(window_dc)
    bitmap = gdi32.CreateCompatibleBitmap(window_dc, width, height)
    old_bitmap = gdi32.SelectObject(memory_dc, bitmap)

    try:
        result = user32.PrintWindow(hwnd, memory_dc, 2)
        if result != 1:
            result = user32.PrintWindow(hwnd, memory_dc, 0)

        bitmap_info = BITMAPINFO()
        bitmap_info.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bitmap_info.bmiHeader.biWidth = width
        bitmap_info.bmiHeader.biHeight = -height
        bitmap_info.bmiHeader.biPlanes = 1
        bitmap_info.bmiHeader.biBitCount = 32
        bitmap_info.bmiHeader.biCompression = 0
        bitmap_info.bmiHeader.biSizeImage = width * height * 4
        pixel_buffer = ctypes.create_string_buffer(bitmap_info.bmiHeader.biSizeImage)
        bits_copied = gdi32.GetDIBits(memory_dc, bitmap, 0, height, pixel_buffer, ctypes.byref(bitmap_info), 0)

        if result == 1 and bits_copied:
            return Image.frombuffer("RGB", (width, height), pixel_buffer, "raw", "BGRX", 0, 1).copy()
    finally:
        gdi32.SelectObject(memory_dc, old_bitmap)
        gdi32.DeleteObject(bitmap)
        gdi32.DeleteDC(memory_dc)
        user32.ReleaseDC(hwnd, window_dc)

    return ImageGrab.grab(bbox=(left, top, right, bottom)).convert("RGB")


def finalize_video_with_audio(raw_video_path: Path, final_output_path: Path) -> Path:
    if AUDIO_INPUT_PATH is None or not AUDIO_INPUT_PATH.exists():
        if raw_video_path != final_output_path:
            raw_video_path.replace(final_output_path)
        return final_output_path

    try:
        import imageio_ffmpeg

        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        result = subprocess.run(
            [
                ffmpeg_exe,
                "-y",
                "-i",
                str(raw_video_path),
                "-i",
                str(AUDIO_INPUT_PATH),
                "-c:v",
                "copy",
                "-c:a",
                "aac",
                "-shortest",
                str(final_output_path),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0 and final_output_path.exists():
            raw_video_path.unlink(missing_ok=True)
            return final_output_path
    except Exception:
        pass

    if raw_video_path != final_output_path:
        raw_video_path.replace(final_output_path)
    return final_output_path


def set_demo_state(app: MainWindow) -> None:
    with app.db.get_connection() as conn:
        conn.execute("DELETE FROM contacts")
        conn.execute("DELETE FROM messages")
        conn.execute("DELETE FROM message_logs")
        conn.commit()

    app.contact_manager.import_from_file(str(SAMPLE_CONTACTS))
    app._reload_contacts()
    for index, variable in enumerate(app.contact_selection_vars.values()):
        variable.set(index < 3)
    app.license_info = LicenseManager.check_license()
    app.license_locked = False
    app._update_license_ui()
    app.session_status_var.set("Persistent session active and ready")

    app.sent_count_var.set("248")
    app.delivered_count_var.set("239")
    app.read_count_var.set("181")
    app.failed_count_var.set("9")
    app.delivery_rate_var.set("96.4%")
    app.reports_feed_var.set("248 sent, 239 delivered, 181 read, 9 failed")
    app.report_export_status_var.set("CSV export ready")
    app.activity_summary_var.set("6 recent events")
    app._replace_text(
        app.activity_text,
        "\n".join(
            [
                "[10:04:21] Campaign dashboard loaded",
                "[10:04:25] 5 contacts imported for demo",
                "[10:04:31] Personalized message preview ready",
                "[10:04:37] Delivery metrics refreshed",
                "[10:04:44] Light theme reviewed successfully",
                "[10:04:51] Reports exported for follow-up",
            ]
        ),
    )
    app._replace_text(
        app.reports_text,
        "\n".join(
            [
                "[READ      ] +923001234567   #84   2026-05-13 10:01",
                "[DELIVERED ] +923009876543   #85   2026-05-13 10:01",
                "[READ      ] +923105551234   #86   2026-05-13 10:02",
                "[DELIVERED ] +923115559876   #87   2026-05-13 10:02",
                "[FAILED    ] +923215678901   #88   2026-05-13 10:03",
            ]
        ),
    )
    app.dashboard_cards["Sent Today"].configure(text="248")
    app.dashboard_cards["Delivery Rate"].configure(text="96.4%")
    app.dashboard_cards["Active Session"].configure(text="Active")
    app.dashboard_cards["License State"].configure(text="Paid")
    app.dashboard_card_meta["Sent Today"].configure(text="3 contacts armed")
    app.dashboard_card_meta["Delivery Rate"].configure(text="Delivered 239 | Read 181")
    app.dashboard_card_meta["Active Session"].configure(text="Persistent session active and ready")
    app.dashboard_card_meta["License State"].configure(text="Commercial license active. Full access is unlocked on this device.")
    app.delivery_progress.set(0.964)
    app.compose_progress.set(0.0)
    app.progress_status_var.set("Ready to launch campaign")
    app._show_view("Dashboard")


def seed_dashboard_metrics(app: MainWindow) -> None:
    app.sent_count_var.set("248")
    app.delivered_count_var.set("239")
    app.read_count_var.set("181")
    app.failed_count_var.set("9")
    app.delivery_rate_var.set("96.4%")
    app.dashboard_cards["Sent Today"].configure(text="248")
    app.dashboard_cards["Delivery Rate"].configure(text="96.4%")
    app.dashboard_cards["Active Session"].configure(text="Active")
    app.dashboard_cards["License State"].configure(text="Paid")
    app.dashboard_card_meta["Sent Today"].configure(text="3 contacts armed")
    app.dashboard_card_meta["Delivery Rate"].configure(text="Delivered 239 | Read 181")
    app.dashboard_card_meta["Active Session"].configure(text="Persistent session active and ready")
    app.dashboard_card_meta["License State"].configure(text="Commercial license active. Full access is unlocked on this device.")


def set_compose_demo(app: MainWindow) -> None:
    for index, variable in enumerate(app.contact_selection_vars.values()):
        variable.set(index < 3)
    app.select_all_var.set(False)
    app.consent_confirmed_var.set(True)
    app.message_textbox.delete("1.0", "end")
    app.message_textbox.insert(
        "1.0",
        "Assalam o Alaikum {name}, your remaining amount is {amount}. Please clear it before {due_date}. Thank you.",
    )
    app._refresh_preview()
    app.progress_status_var.set("Preview ready for 3 selected contacts")


CAPTIONS: list[tuple[float, float, str]] = [
    (0.0, 8.0, "Dashboard overview: one premium control center for campaigns, sessions, and analytics."),
    (8.0, 18.0, "Contacts: import, search, and manage your outreach list from one clean directory."),
    (18.0, 32.0, "Compose: personalize your message, select contacts, and preview before sending."),
    (32.0, 44.0, "Reports: monitor sent, delivered, and read activity with export-ready tracking."),
    (44.0, 54.0, "Settings: control cadence, limits, theme, guardrails, and session management."),
    (54.0, 64.0, "MessageCannon brings contacts, messaging, analytics, and premium workflow into one app."),
    (64.0, 74.0, "Backend visibility: persistent sessions, live activity feeds, and campaign state stay visible in real time."),
    (74.0, 86.0, "Reports intelligence: delivery counters, export status, and audit-ready logs support follow-up and review."),
    (86.0, 96.0, "Operational controls: cadence, daily limits, jitter, and consent guardrails keep sending safer and cleaner."),
    (96.0, DURATION_SECONDS + 0.5, "Final dashboard recap: MessageCannon combines frontend ease with backend-ready monitoring and control."),
]

CURSOR_KEYFRAMES: list[tuple[float, tuple[int, int]]] = [
    (0.0, (1080, 118)),
    (7.2, (1080, 118)),
    (8.0, (106, 265)),
    (11.5, (385, 188)),
    (15.0, (1210, 640)),
    (18.5, (106, 330)),
    (24.7, (478, 603)),
    (32.5, (106, 394)),
    (37.8, (1180, 260)),
    (44.5, (106, 458)),
    (48.0, (1032, 244)),
    (51.5, (1212, 635)),
    (54.0, (1032, 244)),
    (55.5, (106, 201)),
    (60.0, (106, 201)),
    (64.0, (106, 394)),
    (69.0, (1178, 260)),
    (74.0, (106, 458)),
    (80.0, (1040, 246)),
    (84.5, (1210, 636)),
    (90.0, (420, 280)),
    (96.0, (106, 201)),
    (100.0, (790, 560)),
    (DURATION_SECONDS, (790, 560)),
]

CLICK_MOMENTS: list[tuple[float, tuple[int, int]]] = [
    (8.0, (106, 265)),
    (11.5, (385, 188)),
    (18.5, (106, 330)),
    (24.7, (478, 603)),
    (32.5, (106, 394)),
    (37.8, (1180, 260)),
    (44.5, (106, 458)),
    (48.0, (1032, 244)),
    (54.0, (1032, 244)),
    (55.5, (106, 201)),
    (64.0, (106, 394)),
    (74.0, (106, 458)),
    (80.0, (1040, 246)),
    (90.0, (420, 280)),
    (96.0, (106, 201)),
]


def current_caption(seconds_elapsed: float) -> str:
    for start, end, caption in CAPTIONS:
        if start <= seconds_elapsed < end:
            return caption
    return CAPTIONS[-1][2]


def _lerp(start: float, end: float, progress: float) -> float:
    return start + (end - start) * progress


def _ease_out_cubic(progress: float) -> float:
    progress = min(max(progress, 0.0), 1.0)
    return 1.0 - (1.0 - progress) ** 3


def current_cursor_position(seconds_elapsed: float) -> tuple[int, int]:
    if seconds_elapsed <= CURSOR_KEYFRAMES[0][0]:
        return CURSOR_KEYFRAMES[0][1]
    for index in range(len(CURSOR_KEYFRAMES) - 1):
        start_time, start_point = CURSOR_KEYFRAMES[index]
        end_time, end_point = CURSOR_KEYFRAMES[index + 1]
        if start_time <= seconds_elapsed <= end_time:
            if end_time == start_time:
                return end_point
            move_start = max(start_time, end_time - CURSOR_MOVE_SECONDS)
            if seconds_elapsed <= move_start:
                return start_point
            if end_time <= move_start:
                return end_point
            progress = _ease_out_cubic((seconds_elapsed - move_start) / (end_time - move_start))
            return (
                int(_lerp(start_point[0], end_point[0], progress)),
                int(_lerp(start_point[1], end_point[1], progress)),
            )
    return CURSOR_KEYFRAMES[-1][1]


def active_click_progress(seconds_elapsed: float) -> tuple[int, int, float] | None:
    for click_time, click_point in CLICK_MOMENTS:
        if click_time <= seconds_elapsed <= click_time + CLICK_FLASH_SECONDS:
            return click_point[0], click_point[1], (seconds_elapsed - click_time) / CLICK_FLASH_SECONDS
    return None


def should_hold_frame(seconds_elapsed: float) -> bool:
    return any(start <= seconds_elapsed <= end for start, end in FRAME_HOLD_WINDOWS)


def draw_cursor(draw: ImageDraw.ImageDraw, seconds_elapsed: float) -> None:
    return None


def is_transition_blank(frame: Image.Image) -> bool:
    frame_array = np.array(frame, dtype=np.float32)
    content_region = frame_array[110:620, 240:1180]
    std_dev = float(content_region.std())
    mean_value = float(content_region.mean())
    return std_dev < 8.0 and (mean_value < 24.0 or mean_value > 228.0)


def measure_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont | ImageFont.ImageFont) -> tuple[int, int]:
    left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
    return right - left, bottom - top


def fit_caption_lines(draw: ImageDraw.ImageDraw, text: str, max_width: int) -> tuple[ImageFont.FreeTypeFont | ImageFont.ImageFont, list[str]]:
    font_options = [FONT_BODY, FONT_BODY_MEDIUM, FONT_BODY_SMALL, FONT_BODY_XSMALL]
    words = text.split()
    for font in font_options:
        lines: list[str] = []
        current_line = ""
        for word in words:
            candidate = word if not current_line else f"{current_line} {word}"
            candidate_width, _ = measure_text(draw, candidate, font)
            if candidate_width <= max_width:
                current_line = candidate
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word
        if current_line:
            lines.append(current_line)
        if len(lines) <= 2 and all(measure_text(draw, line, font)[0] <= max_width for line in lines):
            return font, lines

    fallback_font = FONT_BODY_XSMALL
    trimmed = text
    while trimmed:
        wrapped = textwrap.wrap(trimmed, width=max(12, max_width // 10))[:2]
        if wrapped:
            last_line = wrapped[-1]
            if len(wrapped) < 2 or measure_text(draw, last_line, fallback_font)[0] <= max_width:
                return fallback_font, wrapped
        trimmed = trimmed[:-4].rstrip()
    return fallback_font, [text[:40]]


def _fade_strength(seconds_elapsed: float, start: float, end: float, fade_window: float = 0.8) -> float:
    if seconds_elapsed < start or seconds_elapsed > end:
        return 0.0
    if seconds_elapsed < start + fade_window:
        return (seconds_elapsed - start) / fade_window
    if seconds_elapsed > end - fade_window:
        return (end - seconds_elapsed) / fade_window
    return 1.0


def draw_intro_outro_overlay(image: Image.Image, seconds_elapsed: float) -> None:
    draw = ImageDraw.Draw(image, "RGBA")
    width, height = image.size

    intro_strength = _fade_strength(seconds_elapsed, 0.0, 2.8, fade_window=0.45)
    if intro_strength > 0:
        alpha = int(150 * intro_strength)
        draw.rounded_rectangle((34, 30, 520, 104), radius=24, fill=(6, 12, 22, alpha))
        draw.rounded_rectangle((52, 46, 56, 88), radius=2, fill=(56, 189, 248, int(220 * intro_strength)))
        draw.text((72, 42), "MESSAGECANNON", font=FONT_TITLE, fill=(245, 249, 252, int(255 * intro_strength)))
        draw.text((72, 70), "Operational walkthrough", font=FONT_SMALL, fill=(188, 210, 223, int(240 * intro_strength)))

    outro_start = max(0.0, DURATION_SECONDS - 3.0)
    outro_strength = _fade_strength(seconds_elapsed, outro_start, DURATION_SECONDS)
    if outro_strength > 0:
        draw.rounded_rectangle((34, height - 96, 488, height - 28), radius=24, fill=(4, 11, 19, int(164 * outro_strength)))
        draw.text((54, height - 78), "Workflow capture complete", font=FONT_META, fill=(247, 250, 252, int(255 * outro_strength)))
        draw.text((54, height - 54), "Faraz Automation", font=FONT_BRAND_CAPTION, fill=(196, 210, 221, int(240 * outro_strength)))


def draw_frame_polish(image: Image.Image) -> None:
    draw = ImageDraw.Draw(image, "RGBA")
    width, height = image.size
    draw.rounded_rectangle((14, 14, width - 14, height - 14), radius=34, outline=(95, 124, 147, 92), width=2)
    draw.rounded_rectangle((24, 24, width - 24, height - 24), radius=30, outline=(18, 28, 42, 120), width=2)


def draw_overlay(image: Image.Image, seconds_elapsed: float) -> Image.Image:
    draw = ImageDraw.Draw(image, "RGBA")
    width, height = image.size
    draw_frame_polish(image)
    draw_intro_outro_overlay(image, seconds_elapsed)
    ribbon_left = 34
    ribbon_top = height - 78
    ribbon_right = width - 34
    ribbon_bottom = height - 30
    draw.rounded_rectangle((ribbon_left, ribbon_top, ribbon_right, ribbon_bottom), radius=20, fill=(5, 10, 20, 172))
    caption_font, caption_lines = fit_caption_lines(draw, current_caption(seconds_elapsed), max(240, ribbon_right - ribbon_left - 180))
    line_height = measure_text(draw, "Ag", caption_font)[1] + 3
    caption_y = ribbon_top + ((ribbon_bottom - ribbon_top - (line_height * len(caption_lines))) // 2) - 1
    for index, line in enumerate(caption_lines):
        draw.text((ribbon_left + 18, caption_y + (index * line_height)), line, font=caption_font, fill="#F8FAFC")
    time_text = f"{seconds_elapsed:04.1f}s"
    time_width, _ = measure_text(draw, time_text, FONT_SMALL)
    draw.text((ribbon_right - time_width - 18, ribbon_top + 14), time_text, font=FONT_SMALL, fill="#E2E8F0")
    draw_cursor(draw, seconds_elapsed)
    return image


def current_backend_panel(seconds_elapsed: float) -> tuple[str, str, list[str]] | None:
    for start, end, title, file_label, lines in BACKEND_CODE_WINDOWS:
        if start <= seconds_elapsed < end:
            return title, file_label, lines
    return None


def current_backend_window(seconds_elapsed: float) -> tuple[float, float, str, str, list[str]] | None:
    for start, end, title, file_label, lines in BACKEND_CODE_WINDOWS:
        if start <= seconds_elapsed < end:
            return start, end, title, file_label, lines
    return None


def _progress_between(seconds_elapsed: float, start: float, end: float) -> float:
    if end <= start:
        return 1.0
    return min(max((seconds_elapsed - start) / (end - start), 0.0), 1.0)


def _visible_code_lines(lines: list[str], progress: float) -> tuple[list[str], int]:
    total_chars = sum(len(line) + 1 for line in lines)
    visible_chars = max(6, int(total_chars * progress))
    visible_lines: list[str] = []
    active_line = 0
    remaining = visible_chars
    for index, line in enumerate(lines):
        if remaining <= 0:
            break
        if remaining >= len(line):
            visible_lines.append(line)
            remaining -= len(line) + 1
            active_line = index
        else:
            visible_lines.append(line[:remaining])
            active_line = index
            remaining = 0
            break
    return visible_lines, active_line


def _code_segments(line: str) -> list[tuple[str, str]]:
    if not line:
        return [("", "#D7E8F4")]
    comment_start = line.find("#")
    code_part = line if comment_start < 0 else line[:comment_start]
    comment_part = "" if comment_start < 0 else line[comment_start:]
    segments: list[tuple[str, str]] = []
    for token in re.findall(r'\s+|"[^"]*"|\'[^"]*\'|\b[A-Za-z_][A-Za-z0-9_]*\b|\d+|.', code_part):
        color = "#D7E8F4"
        if token.strip() in PYTHON_KEYWORDS:
            color = "#7CC7FF"
        elif token.startswith(("\"", "'")):
            color = "#F7C07A"
        elif token.isdigit():
            color = "#C792EA"
        elif token in {"self", "contacts", "messages", "state", "tracked_id", "event_callback"}:
            color = "#82E6C5"
        elif token and token[0].isupper() and token[0].isalpha():
            color = "#4EC9B0"
        segments.append((token, color))
    if comment_part:
        segments.append((comment_part, "#7FB27F"))
    return segments


def _draw_syntax_line(draw: ImageDraw.ImageDraw, x: int, y: int, line: str) -> None:
    cursor_x = x
    for token, color in _code_segments(line):
        if token:
            draw.text((cursor_x, y), token, font=FONT_CODE, fill=color)
            cursor_x += measure_text(draw, token, FONT_CODE)[0]


def _backend_terminal_lines(title: str) -> list[str]:
    if title == "Python Backend":
        return [
            "> python src/main.py",
            "[INFO] Loaded persisted browser profile",
            "[INFO] Session TTL: 48h | Active session available",
            "[INFO] Startup splash initialized successfully",
        ]
    if title == "Delivery Tracking":
        return [
            "> python -m src.delivery_tracker",
            "[INFO] Delivery report queue attached to SQLite",
            "[INFO] Pollable statuses: sent, delivered",
            "[INFO] Export report worker ready for CSV / PDF",
        ]
    return [
        "> python -m src.core.whatsapp_sender --dry-run",
        "[INFO] 3 contacts queued with controlled cadence",
        "[INFO] Message echo received | status: sent",
        "[INFO] Delivery tracker updated recent activity feed",
    ]


def _backend_editor_tabs(title: str) -> list[tuple[str, bool]]:
    if title == "Python Backend":
        return [
            ("src/main.py", False),
            ("src/session_manager.py", True),
            ("src/ui/main_window.py", False),
        ]
    if title == "Delivery Tracking":
        return [
            ("src/delivery_tracker.py", True),
            ("reports/export_worker.py", False),
            ("reports.sqlite", False),
        ]
    return [
        ("src/core/whatsapp_sender.py", True),
        ("src/delivery_tracker.py", False),
        ("terminal", False),
    ]


def _visible_terminal_lines(lines: list[str], progress: float) -> list[str]:
    count = min(len(lines), max(1, int(math.ceil(progress * len(lines)))))
    return lines[:count]


def draw_backend_code_overlay(draw: ImageDraw.ImageDraw, width: int, height: int, seconds_elapsed: float) -> None:
    panel = current_backend_window(seconds_elapsed)
    if panel is None:
        return

    start, end, title, file_label, lines = panel
    progress = _progress_between(seconds_elapsed, start, end)
    visible_lines, active_line = _visible_code_lines(lines, progress)

    panel_left = 654
    panel_top = 74
    panel_right = width - 36
    panel_bottom = height - 146
    gutter_width = 42
    line_height = 25
    activity_bar_width = 32
    topbar_height = 34
    tabbar_height = 36
    terminal_height = 112

    draw.rounded_rectangle((panel_left, panel_top, panel_right, panel_bottom), radius=22, fill=(8, 12, 20, 244), outline=(38, 67, 94, 255), width=2)
    draw.rounded_rectangle((panel_left, panel_top, panel_right, panel_top + topbar_height), radius=22, fill=(23, 28, 38, 255))
    draw.rectangle((panel_left, panel_top + 18, panel_right, panel_top + topbar_height), fill=(23, 28, 38, 255))

    traffic_y = panel_top + 12
    for index, color in enumerate([(255, 95, 86), (255, 189, 46), (39, 201, 63)]):
        cx = panel_left + 18 + (index * 16)
        draw.ellipse((cx, traffic_y, cx + 10, traffic_y + 10), fill=color)
    draw.text((panel_left + 74, panel_top + 9), "Visual Studio Code", font=FONT_SMALL, fill="#9FB5C3")

    tab_top = panel_top + topbar_height
    draw.rectangle((panel_left, tab_top, panel_right, tab_top + tabbar_height), fill=(16, 21, 30, 255))
    tab_x = panel_left + 52
    for tab_label, is_active in _backend_editor_tabs(title):
        tab_width = max(118, measure_text(draw, tab_label, FONT_SMALL)[0] + 34)
        draw.rounded_rectangle(
            (tab_x, tab_top + 5, tab_x + tab_width, tab_top + 31),
            radius=10,
            fill=(31, 43, 58, 255) if is_active else (19, 27, 38, 255),
        )
        draw.text((tab_x + 14, tab_top + 11), tab_label, font=FONT_SMALL, fill="#E6F0F7" if is_active else "#6F8796")
        if is_active:
            draw.text((tab_x + tab_width - 18, tab_top + 11), "●", font=FONT_SMALL, fill="#7DD3FC")
        tab_x += tab_width + 8

    editor_top = tab_top + tabbar_height
    terminal_top = panel_bottom - terminal_height
    draw.rectangle((panel_left, editor_top, panel_left + activity_bar_width, terminal_top), fill=(19, 24, 34, 255))
    draw.text((panel_left + 10, editor_top + 22), "F", font=FONT_SMALL, fill="#7CC7FF")
    draw.text((panel_left + 10, editor_top + 56), "S", font=FONT_SMALL, fill="#6F8796")
    draw.text((panel_left + 10, editor_top + 90), "G", font=FONT_SMALL, fill="#6F8796")

    editor_left = panel_left + activity_bar_width
    draw.rectangle((editor_left, editor_top, panel_right, terminal_top), fill=(11, 17, 28, 255))
    draw.rectangle((editor_left, terminal_top, panel_right, panel_bottom), fill=(12, 20, 29, 255))
    draw.rectangle((editor_left, terminal_top, panel_right, terminal_top + 28), fill=(18, 27, 38, 255))
    draw.text((editor_left + 16, terminal_top + 7), title + "  •  Python 3.11", font=FONT_SMALL, fill="#B8CAD6")

    code_top = editor_top + 14
    code_right = panel_right - 16
    draw.rounded_rectangle((editor_left + 10, code_top - 8, code_right, terminal_top - 14), radius=14, fill=(10, 17, 28, 255))

    for index, line in enumerate(visible_lines, start=1):
        y = code_top + ((index - 1) * line_height)
        if y + line_height > terminal_top - 22:
            break
        if index - 1 == active_line:
            draw.rounded_rectangle((editor_left + 16, y - 2, code_right - 8, y + 20), radius=8, fill=(21, 32, 45, 220))
        draw.text((editor_left + 20, y), f"{index:>2}", font=FONT_SMALL, fill="#5D7483")
        _draw_syntax_line(draw, editor_left + 20 + gutter_width, y, line)

    if visible_lines:
        active_text = visible_lines[min(active_line, len(visible_lines) - 1)]
        prefix_width = measure_text(draw, active_text, FONT_CODE)[0]
        cursor_x = editor_left + 20 + gutter_width + prefix_width + 2
        cursor_y = code_top + (min(active_line, len(visible_lines) - 1) * line_height)
        if int(seconds_elapsed * 2) % 2 == 0:
            draw.rectangle((cursor_x, cursor_y + 2, cursor_x + 2, cursor_y + 19), fill="#E6F0F7")

    terminal_lines = _visible_terminal_lines(_backend_terminal_lines(title), progress)
    prompt_blink = "_" if int(seconds_elapsed * 2) % 2 == 0 else ""
    for index, line in enumerate(terminal_lines):
        y = terminal_top + 38 + (index * 22)
        _draw_syntax_line(draw, editor_left + 18, y, line)
    if terminal_lines:
        draw.text((editor_left + 18, terminal_top + 38 + (len(terminal_lines) * 22)), prompt_blink, font=FONT_CODE, fill="#E6F0F7")

    status_bar_top = panel_bottom - 22
    draw.rectangle((panel_left, status_bar_top, panel_right, panel_bottom), fill=(0, 122, 204, 255))
    draw.text((panel_left + 14, status_bar_top + 4), "Python  •  UTF-8  •  LF", font=FONT_SMALL, fill="#FFFFFF")
    draw.text((panel_right - 182, status_bar_top + 4), f"{file_label}  •  Ln 18, Col 24", font=FONT_SMALL, fill="#FFFFFF")


def capture_loop(app: MainWindow, done_event: threading.Event) -> None:
    hwnd = app.winfo_id()
    writer = imageio.get_writer(str(RAW_OUTPUT_PATH), fps=FPS)
    time.sleep(START_DELAY_MS / 1000)
    focus_window(hwnd)
    start_time = time.time()
    frame_count = 0
    target_frame_count = DURATION_SECONDS * FPS
    last_frame_array: np.ndarray | None = None
    last_good_base_frame: Image.Image | None = None
    try:
        while not done_event.is_set():
            frame = capture_window_frame(hwnd)
            frame = frame.resize(FRAME_SIZE, Image.Resampling.LANCZOS)
            elapsed = time.time() - start_time
            last_good_base_frame = frame.copy()
            frame = draw_overlay(frame, elapsed)
            last_frame_array = np.array(frame)
            target_frames_by_now = min(target_frame_count, max(frame_count + 1, int(round(elapsed * FPS))))
            while frame_count < target_frames_by_now:
                writer.append_data(last_frame_array)
                frame_count += 1
            if elapsed >= DURATION_SECONDS:
                done_event.set()
                break
            time.sleep(max(0.0, (1.0 / FPS) - 0.01))
    finally:
        if last_frame_array is not None:
            while frame_count < target_frame_count:
                writer.append_data(last_frame_array)
                frame_count += 1
        writer.close()


def schedule_actions(app: MainWindow, done_event: threading.Event) -> None:
    def run(action: Callable[[], None]) -> Callable[[], None]:
        def wrapper() -> None:
            if done_event.is_set():
                return
            app.lift()
            app.focus_force()
            focus_window(app.winfo_id())
            action()
            app.update_idletasks()
        return wrapper

    def dashboard_intro() -> None:
        app._show_view("Dashboard")
        app.header_badge_var.set("Premium Campaign Workspace")
        seed_dashboard_metrics(app)

    def contacts_view() -> None:
        app._show_view("Contacts")

    def contacts_search() -> None:
        app.search_var.set("Ali")
        app._render_contacts_directory()

    def contacts_clear_and_scroll() -> None:
        app.search_var.set("")
        app._render_contacts_directory()
        canvas = getattr(app.contacts_directory, "_parent_canvas", None)
        if canvas is not None:
            canvas.yview_moveto(1.0)

    def compose_view() -> None:
        app._show_view("Compose")
        set_compose_demo(app)

    def compose_insert_variable() -> None:
        app.message_textbox.insert("end", " Please contact us if you need support.")
        app._refresh_preview()

    def reports_view() -> None:
        app._show_view("Reports")
        app.delivery_progress.set(0.964)

    def reports_update() -> None:
        app.sent_count_var.set("248")
        app.delivered_count_var.set("241")
        app.read_count_var.set("186")
        app.failed_count_var.set("7")
        app.delivery_rate_var.set("97.2%")
        app.reports_feed_var.set("248 sent, 241 delivered, 186 read, 7 failed")
        app.delivery_progress.set(0.972)

    def settings_view() -> None:
        app._show_view("Settings")

    def settings_adjust_delay() -> None:
        app.delay_var.set(45)
        app.delay_slider.set(app.delay_var.get())
        app.delay_label.configure(text=f"{app.delay_var.get()} sec")
        app.limit_warning_label.configure(text="Balanced cadence enabled for stable sending")

    def settings_adjust_limit() -> None:
        app.daily_limit_var.set(120)
        app.limit_slider.set(app.daily_limit_var.get())
        app.limit_label.configure(text=str(app.daily_limit_var.get()))

    def settings_guardrails() -> None:
        app.jitter_var.set(True)
        app.consent_required_var.set(True)
        app._save_settings()

    def settings_scroll() -> None:
        settings_frame = app.view_frames["Settings"]
        canvas = getattr(settings_frame, "_parent_canvas", None)
        if canvas is not None:
            canvas.yview_moveto(1.0)

    def final_dashboard() -> None:
        app._show_view("Dashboard")
        app.activity_summary_var.set("Demo ready")
        seed_dashboard_metrics(app)

    def backend_dashboard_sync() -> None:
        app._show_view("Dashboard")
        app.header_badge_var.set("Backend Monitoring Layer")
        app.header_context_var.set("Session health, pacing rules, export state, and delivery movement stay visible during campaigns.")
        app.session_status_var.set("Persistent session active. Browser heartbeat synced 8 seconds ago.")
        app.activity_summary_var.set("9 backend events")
        app.sent_count_var.set("312")
        app.delivered_count_var.set("301")
        app.read_count_var.set("227")
        app.failed_count_var.set("11")
        app.delivery_rate_var.set("96.5%")
        app.dashboard_cards["Sent Today"].configure(text="312")
        app.dashboard_cards["Delivery Rate"].configure(text="96.5%")
        app.dashboard_cards["Active Session"].configure(text="Stable")
        app.dashboard_cards["License State"].configure(text="Paid")
        app.dashboard_card_meta["Sent Today"].configure(text="Queue running with controlled pacing")
        app.dashboard_card_meta["Delivery Rate"].configure(text="Delivered 301 | Read 227")
        app.dashboard_card_meta["Active Session"].configure(text="Persistent session heartbeat confirmed")
        app.dashboard_card_meta["License State"].configure(text="Commercial license active for backend workflow")
        app._replace_text(
            app.activity_text,
            "\n".join(
                [
                    "[10:05:08] Session heartbeat confirmed from saved browser state",
                    "[10:05:15] Rate-limit guardrails loaded from campaign profile",
                    "[10:05:24] Delivery worker resumed with 3-message queue",
                    "[10:05:31] Preview merge validated for contact placeholders",
                    "[10:05:39] Delivery callback marked 4 more reads",
                    "[10:05:46] Reports feed prepared for CSV and PDF export",
                    "[10:05:54] Theme and recovery settings persisted locally",
                    "[10:06:01] Background monitoring remained stable",
                    "[10:06:08] Dashboard KPI tiles refreshed successfully",
                ]
            ),
        )

    def backend_reports_view() -> None:
        app._show_view("Reports")
        app.report_format_var.set("pdf")
        app._update_report_summary()
        app.sent_count_var.set("312")
        app.delivered_count_var.set("304")
        app.read_count_var.set("233")
        app.failed_count_var.set("8")
        app.delivery_rate_var.set("97.4%")
        app.reports_feed_var.set("312 sent, 304 delivered, 233 read, 8 failed")
        app.report_export_status_var.set("PDF executive export prepared")
        app.delivery_progress.set(0.974)
        app._replace_text(
            app.reports_text,
            "\n".join(
                [
                    "[READ      ] +923001234567   #091   2026-05-13 10:05",
                    "[DELIVERED ] +923009876543   #092   2026-05-13 10:05",
                    "[READ      ] +923105551234   #093   2026-05-13 10:06",
                    "[DELIVERED ] +923115559876   #094   2026-05-13 10:06",
                    "[QUEUED    ] +923215678901   #095   2026-05-13 10:06",
                    "[READ      ] +923221112233   #096   2026-05-13 10:07",
                    "[DELIVERED ] +923331234567   #097   2026-05-13 10:07",
                    "[READ      ] +923441234567   #098   2026-05-13 10:08",
                ]
            ),
        )

    def backend_settings_view() -> None:
        app._show_view("Settings")
        app.delay_var.set(45)
        app.daily_limit_var.set(120)
        app.jitter_var.set(True)
        app.consent_required_var.set(True)
        app.delay_slider.set(app.delay_var.get())
        app.limit_slider.set(app.daily_limit_var.get())
        app.delay_label.configure(text=f"{app.delay_var.get()} sec")
        app.limit_label.configure(text=str(app.daily_limit_var.get()))
        app.limit_warning_label.configure(text="Balanced throughput for safer long campaigns")
        app._save_settings()

    def backend_theme_light() -> None:
        app._on_theme_selected("Light")

    def backend_theme_dark() -> None:
        app._on_theme_selected("Dark")

    def backend_compose_review() -> None:
        app._show_view("Compose")
        set_compose_demo(app)
        app.compose_progress.set(0.66)
        app.progress_status_var.set("Backend queue validated for the next 3 contacts")
        app.message_textbox.delete("1.0", "end")
        app.message_textbox.insert(
            "1.0",
            "Assalam o Alaikum {name}, your pending balance is {amount}. Backend session is active and follow-up is queued before {due_date}.",
        )
        app._refresh_preview()

    def backend_final_dashboard() -> None:
        app._show_view("Dashboard")
        app.header_badge_var.set("Campaign Control Center")
        app.header_context_var.set("One desktop workflow for sessions, messaging, tracking, exports, and safer campaign operations.")
        app.activity_summary_var.set("Launch ready")
        app.sent_count_var.set("312")
        app.delivered_count_var.set("304")
        app.read_count_var.set("233")
        app.failed_count_var.set("8")
        app.delivery_rate_var.set("97.4%")
        app.dashboard_cards["Sent Today"].configure(text="312")
        app.dashboard_cards["Delivery Rate"].configure(text="97.4%")
        app.dashboard_cards["Active Session"].configure(text="Stable")
        app.dashboard_cards["License State"].configure(text="Premium")
        app.dashboard_card_meta["Sent Today"].configure(text="Contacts, queue, and reports aligned")
        app.dashboard_card_meta["Delivery Rate"].configure(text="Delivered 304 | Read 233")
        app.dashboard_card_meta["Active Session"].configure(text="Persistent session ready for the next run")
        app.dashboard_card_meta["License State"].configure(text="Premium desktop workflow unlocked")

    def finish() -> None:
        done_event.set()
        app.after(600, app.destroy)

    timeline = [
        (START_DELAY_MS + 0, dashboard_intro),
        (START_DELAY_MS + 8500, contacts_view),
        (START_DELAY_MS + 11500, contacts_search),
        (START_DELAY_MS + 15000, contacts_clear_and_scroll),
        (START_DELAY_MS + 18500, compose_view),
        (START_DELAY_MS + 25000, compose_insert_variable),
        (START_DELAY_MS + 32500, reports_view),
        (START_DELAY_MS + 38000, reports_update),
        (START_DELAY_MS + 44500, settings_view),
        (START_DELAY_MS + 48000, settings_adjust_delay),
        (START_DELAY_MS + 51500, settings_scroll),
        (START_DELAY_MS + 54000, settings_adjust_limit),
        (START_DELAY_MS + 55200, settings_guardrails),
        (START_DELAY_MS + 55500, final_dashboard),
        (START_DELAY_MS + 64000, backend_dashboard_sync),
        (START_DELAY_MS + 74000, backend_reports_view),
        (START_DELAY_MS + 86000, backend_settings_view),
        (START_DELAY_MS + 90000, backend_theme_light),
        (START_DELAY_MS + 94000, backend_theme_dark),
        (START_DELAY_MS + 96000, backend_compose_review),
        (START_DELAY_MS + 100000, backend_final_dashboard),
        (START_DELAY_MS + int(DURATION_SECONDS * 1000), finish),
    ]
    for delay, action in timeline:
        app.after(delay, run(action))


def main() -> None:
    patch_demo_mode()
    done_event = threading.Event()
    app = MainWindow()
    app.geometry(WINDOW_GEOMETRY)
    app.attributes("-topmost", True)
    app.update_idletasks()
    app.lift()
    app.focus_force()
    focus_window(app.winfo_id())
    for delay in (300, 900, 1500):
        app.after(delay, app.lift)
        app.after(delay, app.focus_force)
    set_demo_state(app)
    schedule_actions(app, done_event)
    recorder = threading.Thread(target=capture_loop, args=(app, done_event), daemon=True)
    recorder.start()
    app.mainloop()
    done_event.set()
    recorder.join(timeout=10)
    final_output_path = finalize_video_with_audio(RAW_OUTPUT_PATH, OUTPUT_PATH)
    print(final_output_path)


if __name__ == "__main__":
    main()
