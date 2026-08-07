"""One-shot, tight demo/proof script for tour.py's hover-to-discover mode --
not part of the shipped app. Drives the real TourMode through 4 real
discoveries (warping the real OS cursor near each real widget first, so the
cursor-follow animation has a sensible real position to chase), letting the
real .after()-scheduled fade/follow animations settle, then captures a real
screenshot cropped to the app window's own bounding box after each one.

Run: python scripts/demo_tour_mode.py
Output: PNGs under the path given as sys.argv[1] (a scratch directory).
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

OUT_DIR = Path(sys.argv[1]) if len(sys.argv) > 1 else PROJECT_ROOT / "_tour_demo"
OUT_DIR.mkdir(parents=True, exist_ok=True)

import tests.ui.conftest  # noqa: E402  (mocks WhatsApp bootstrap + update check)
from PIL import ImageGrab  # noqa: E402

from src.ui.main_window import MainWindow  # noqa: E402
from src.ui.tour import _hover_target, _work_area_bottom  # noqa: E402


def pump(window, seconds: float) -> None:
    deadline = time.time() + seconds
    while time.time() < deadline:
        window.update()
        time.sleep(0.01)


def scroll_into_view(panel, widget) -> None:
    """Demo-only convenience: the Card Identity panel is a real
    CTkScrollableFrame (Item 18), and the template gallery isn't always in
    the default viewport -- a real user would scroll to see it, same as
    this does, before hovering it. Computed analytically (offset within the
    real scrollregion vs. the real viewport height) rather than guessed, so
    the target lands roughly centered instead of clipped at an edge."""
    canvas = getattr(panel, "_parent_canvas", None)
    if canvas is None:
        return
    canvas.yview_moveto(0.0)
    panel.update_idletasks()
    local_offset = widget.winfo_rooty() - panel.winfo_rooty()
    viewport_h = panel.winfo_height()
    bbox = canvas.bbox("all")
    total_h = bbox[3] - bbox[1] if bbox else viewport_h
    if total_h <= viewport_h:
        return
    frac = (local_offset - viewport_h / 2) / (total_h - viewport_h)
    canvas.yview_moveto(max(0.0, min(1.0, frac)))
    panel.update_idletasks()


def warp_to(widget) -> None:
    target = _hover_target(widget)
    target.update_idletasks()
    cx = target.winfo_width() // 2
    cy = target.winfo_height() // 2
    target.event_generate("<Motion>", warp=True, x=cx, y=cy)


def capture(window, window_x, window_y, window_w, window_h, label: str) -> None:
    # Deliberately NO margin beyond the app's own real window rect (a first
    # pass with a 40px margin bled into the real Windows taskbar at the
    # bottom of the screen -- exposing pinned taskbar icons that have
    # nothing to do with this app). Clamped tightly to the window's own
    # bounds only, plus a hard clamp to the real screen size as a second
    # safety net.
    x0 = max(0, window_x)
    y0 = max(0, window_y)
    x1 = min(window.winfo_screenwidth(), window_x + window_w)
    y1 = min(_work_area_bottom(window.winfo_screenheight()), window_y + window_h)
    img = ImageGrab.grab(bbox=(x0, y0, x1, y1))
    path = OUT_DIR / f"{label}.png"
    img.save(path)
    print(f"Saved {path} ({img.width}x{img.height})")


def main() -> None:
    window = MainWindow()
    window.update()
    pump(window, 0.3)

    tour = window.tour_mode
    tour.enable()
    window.update()

    window.update_idletasks()
    wx, wy = window.winfo_rootx(), window.winfo_rooty()
    ww, wh = window.winfo_width(), window.winfo_height()

    # 1: Campaigns nav button (already the active view)
    warp_to(window.sidebar_buttons["Campaigns"])
    window.update()
    tour._on_enter("campaigns")
    pump(window, 0.5)
    capture(window, wx, wy, ww, wh, "1_campaigns_sidebar")

    # 2: Contacts nav button
    tour._on_leave("campaigns")
    warp_to(window.sidebar_buttons["Contacts"])
    window.update()
    tour._on_enter("contacts")
    pump(window, 0.5)
    capture(window, wx, wy, ww, wh, "2_contacts_sidebar")

    # 3: Compose's "Generate with AI" button (navigate there first, exactly
    # like a real user would, then hover the real button)
    tour._on_leave("contacts")
    pump(window, 0.2)
    window._show_view("Compose")
    window.update()
    warp_to(window.wa_generate_ai_btn)
    window.update()
    tour._on_enter("generate_ai")
    pump(window, 0.5)
    capture(window, wx, wy, ww, wh, "3_compose_generate_with_ai")

    # 4: Card Creator's template gallery (navigate there, hover a real
    # thumbnail)
    tour._on_leave("generate_ai")
    pump(window, 0.2)
    window._show_view("Cards")
    window.update()
    tab = window.card_creator_tab
    thumb = tab._template_thumb_canvases.get("Dark Premium") or next(
        iter(tab._template_thumb_canvases.values()))
    scroll_into_view(tab._card_identity_panel, thumb)
    window.update()
    warp_to(thumb)
    window.update()
    tour._on_enter("card_gallery")
    pump(window, 0.5)
    capture(window, wx, wy, ww, wh, "4_card_template_gallery")

    print("discovered:", tour.discovered_count, "of", tour.total_count, tour._discovered)

    tour._on_leave("card_gallery")
    pump(window, 0.3)
    tour.disable()
    window.update()
    window.destroy()
    print("DONE")


if __name__ == "__main__":
    main()
