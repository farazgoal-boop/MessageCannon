"""Item 39 v2 (2026-08-08): cursor-following "hover to discover" tour mode.

Replaces the original click-through-cards guided tour (a fixed Next/Back
sequence over a modal dialog) after live feedback that it felt generic and
forgettable. The new mechanic: toggle "Tour Mode" on, and the real app stays
fully interactive underneath — as the mouse moves near a real feature
(sidebar nav, Compose's "Generate with AI" button, the Card Creator's
template gallery, the sidebar update badge, ...), a small floating detail
card smoothly chases the cursor and explains exactly what's under it, with
the actual widget outlined by a real spotlight ring. There is no forced
order — the user explores at their own pace, in one continuous pass, and a
small persistent "X of Y explored" indicator (with an Exit Tour button)
keeps the exploration feeling complete-able rather than aimless.

Why this shape, given what this stack can and can't do (same discipline as
every other UI decision in this app — see CLAUDE.md for the precedent on
the signature view-transition animation and the sidebar's own gradient
accent bar, both hit and documented the same limitation): CustomTkinter/Tk
has no per-widget alpha, no CSS `:hover` reveal, and no way to draw
arbitrary content *floating above* an existing widget without a second, real
window. So every piece of this feature — the spotlight ring, the detail
card, the cursor glow, the "discovered" checkmark badges — is a small, real,
separately-positioned `CTkToplevel` (`overrideredirect` + `-topmost`, the
same technique already proven by `toast.py`/`tooltip.py`), continuously
repositioned against the real target widget's or the real cursor's own
on-screen coordinates. Two of them (the card and the cursor glow) get a
genuine alpha fade in/out — `-alpha` is a real, already-working whole-window
attribute on this exact stack (`toast.py` already sets a static one) — and
the cursor glow additionally uses Tk's own `-transparentcolor` attribute
(Windows-only, gracefully absent elsewhere) so it renders as a real soft
circular dot instead of a colored square.

Click-through is the one piece of this that's genuinely new engineering for
this app (though the *pattern* — a small, disclosed, try/except-wrapped
ctypes call, same as `utils/dpi.py`'s DPI-awareness call — is already
established precedent): every purely-visual overlay here (ring, card, glow,
badges) is marked `WS_EX_LAYERED | WS_EX_TRANSPARENT` via ctypes on Windows,
so it can sit directly on top of a real button — including exactly at the
cursor's own position, where the glow dot lives — without ever stealing a
click meant for the real widget underneath it. Only the persistent progress
HUD (the "X of Y explored" + "Exit Tour" panel) is a normal, real, clickable
window, since its Exit Tour button has to actually receive clicks.
"""

from __future__ import annotations

import sys
import tkinter as tk
from typing import Callable, Dict, List, Optional, Set, Tuple, TypedDict

import customtkinter as ctk

from . import theme as T

RING_THICKNESS = 3
RING_PADDING = 6

CARD_WIDTH = 300
CARD_HEIGHT_ESTIMATE = 110
CARD_OFFSET_X = 24
CARD_OFFSET_Y = 20
CARD_EASE = 0.28

GLOW_DIAMETER = 16
GLOW_EASE = 0.6

FOLLOW_TICK_MS = 16
FADE_STEPS = 6
FADE_STEP_MS = 16
HIDE_DELAY_MS = 110

BADGE_DIAMETER = 18
BADGE_REFRESH_MS = 260

# A deliberately unlikely-to-collide sentinel color, keyed transparent via
# Tk's own `-transparentcolor` (Windows only) so the glow dot and discovery
# badges render as real circles, not colored squares.
_TRANSPARENT_KEY = "#FE01FE"


def _make_click_through(window) -> None:
    """Marks `window` so mouse events pass straight through it to whatever
    real widget is underneath — required for any overlay that might end up
    positioned exactly where the cursor is (the glow dot always is). Real
    Win32 API via ctypes, same disclosed-precedent pattern as
    `utils/dpi.py`'s DPI-awareness call: a plain, try/except-wrapped,
    platform-gated call, never assumed to succeed. No-op (a small, accepted
    fidelity loss, not a crash) on non-Windows."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        GWL_EXSTYLE = -20
        WS_EX_LAYERED = 0x00080000
        WS_EX_TRANSPARENT = 0x00000020
        GA_ROOT = 2
        hwnd = ctypes.windll.user32.GetAncestor(window.winfo_id(), GA_ROOT)
        style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        ctypes.windll.user32.SetWindowLongW(
            hwnd, GWL_EXSTYLE, style | WS_EX_LAYERED | WS_EX_TRANSPARENT)
    except Exception:
        pass


def _work_area_bottom(fallback: int) -> int:
    """The real, taskbar-excluded desktop work-area bottom edge (Windows
    `SPI_GETWORKAREA`) -- found while producing this feature's own demo
    screenshots: clamping the cursor-follow card against
    `winfo_screenheight()` (the FULL screen, taskbar included) let the card
    render partially behind/under the real Windows taskbar whenever the
    cursor was near the bottom of the screen, on any real machine with a
    visible taskbar, not just this dev one. Falls back to the full screen
    height (the previous behavior) on any failure or non-Windows, which is
    the correct degrade — a slightly-too-low clamp, never a crash."""
    if sys.platform != "win32":
        return fallback
    try:
        import ctypes
        import ctypes.wintypes as wt
        rect = wt.RECT()
        SPI_GETWORKAREA = 0x0030
        ok = ctypes.windll.user32.SystemParametersInfoW(SPI_GETWORKAREA, 0, ctypes.byref(rect), 0)
        if ok and rect.bottom > 0:
            return rect.bottom
    except Exception:
        pass
    return fallback


def _try_transparent_color(window, color: str) -> bool:
    """Best-effort per-pixel color-key transparency (Windows Tk only) so a
    small circular overlay renders as a real circle instead of a colored
    square. Returns whether it took effect, so the caller can choose a
    normal opaque fallback background otherwise."""
    try:
        window.attributes("-transparentcolor", color)
        return True
    except Exception:
        return False


def _hover_target(widget):
    """CustomTkinter draws every interactive widget on an internal Tk
    Canvas, not the outer wrapper — real mouse Enter/Leave land on that
    canvas, not the CTkButton/CTkFrame object itself. Same real target
    `accessibility.py` already established for this exact reason (its own
    docstring covers the direct confirmation). Plain `tk.Canvas` widgets
    (e.g. a template-gallery thumbnail) have no such wrapper and are their
    own real target already."""
    canvas = getattr(widget, "_canvas", None)
    return canvas if canvas is not None else widget


class DiscoverableItem(TypedDict):
    id: str
    icon: str
    title: str
    description: str
    getter: Callable[[object], Optional[object]]


def _first_template_thumb(main_window):
    tab = getattr(main_window, "card_creator_tab", None)
    if tab is None:
        return None
    canvases = getattr(tab, "_template_thumb_canvases", None)
    if not canvases:
        return None
    return canvases.get("Dark Premium") or next(iter(canvases.values()), None)


DISCOVERABLE_ITEMS: List[DiscoverableItem] = [
    {
        "id": "campaigns", "icon": "⊞", "title": "Campaigns Dashboard",
        "description": "Your home base — recent campaigns, real send/delivery "
                        "stats, and a 7-day sending trend at a glance.",
        "getter": lambda mw: mw.sidebar_buttons.get("Campaigns"),
    },
    {
        "id": "contacts", "icon": "☰", "title": "Contacts",
        "description": "Import contacts from CSV/Excel with a real review step — "
                        "duplicates and bad numbers are flagged with a clear "
                        "reason before anything is saved.",
        "getter": lambda mw: mw.sidebar_buttons.get("Contacts"),
    },
    {
        "id": "compose", "icon": "✉", "title": "Compose",
        "description": "Write once, personalize per contact — Email and WhatsApp "
                        "share one screen with live, real preview.",
        "getter": lambda mw: mw.sidebar_buttons.get("Compose"),
    },
    {
        "id": "generate_ai", "icon": "✨", "title": "Generate with AI",
        "description": "Drafts real message copy and true per-recipient "
                        "variations from your own imported data, using your own "
                        "AI key.",
        "getter": lambda mw: getattr(mw, "wa_generate_ai_btn", None),
    },
    {
        "id": "cards", "icon": "❏", "title": "Card Creator",
        "description": "Design a real marketing card — image, price, discount, "
                        "and a working Buy Now button — then send it for real.",
        "getter": lambda mw: mw.sidebar_buttons.get("Cards"),
    },
    {
        "id": "card_gallery", "icon": "🎨", "title": "Card Template Gallery",
        "description": "Pick a real visual starting point, or save your own as "
                        "a reusable template.",
        "getter": _first_template_thumb,
    },
    {
        "id": "history", "icon": "◈", "title": "Delivery & Bounce Tracking",
        "description": "After a campaign sends, MessageCannon checks your real "
                        "inbox for bounces — an honest Sent/Bounced/Delivered "
                        "breakdown, not a guess.",
        "getter": lambda mw: mw.sidebar_buttons.get("History"),
    },
    {
        "id": "settings", "icon": "⚙", "title": "Settings & License",
        "description": "Connect your email/WhatsApp, set safe sending limits, "
                        "and manage your license — all local to this device.",
        "getter": lambda mw: mw.sidebar_buttons.get("Settings"),
    },
    {
        "id": "update_badge", "icon": "⬆", "title": "Automatic Updates",
        "description": "A badge appears right here when a new version is "
                        "published — one click downloads and installs it.",
        "getter": lambda mw: getattr(mw, "_update_badge_slot", None),
    },
    {
        "id": "tour_button", "icon": "🧭", "title": "This Tour",
        "description": "You found the tour toggle itself — click it anytime to "
                        "start a fresh, self-paced exploration.",
        "getter": lambda mw: getattr(mw, "header_tour_btn", None),
    },
]


class _OverlayToplevel:
    """Shared construction for the small always-on-top windows this feature
    is built from — starts fully transparent and unmapped so nothing flashes
    into view before its first real position/fade-in."""

    def __init__(self, master, click_through: bool = True):
        self.win = ctk.CTkToplevel(master)
        self.win.overrideredirect(True)
        try:
            self.win.attributes("-topmost", True)
        except Exception:
            pass
        try:
            self.win.attributes("-alpha", 0.0)
        except Exception:
            pass
        if click_through:
            _make_click_through(self.win)
        self.win.withdraw()

    def show(self) -> None:
        try:
            self.win.deiconify()
        except Exception:
            pass

    def hide(self) -> None:
        try:
            self.win.withdraw()
        except Exception:
            pass

    def set_alpha(self, alpha: float) -> None:
        try:
            self.win.attributes("-alpha", max(0.0, min(1.0, alpha)))
        except Exception:
            pass

    def destroy(self) -> None:
        try:
            self.win.destroy()
        except Exception:
            pass


class _SpotlightRing:
    """Four thin, always-on-top, click-through bars forming a rectangular
    accent-colored outline around a target widget's real screen bounds —
    unchanged in spirit from the original Item 39 implementation, kept as
    the "real element highlighted" half of this feature per the redesign's
    own explicit requirement."""

    def __init__(self, master):
        self._bars = [self._make_bar(master) for _ in range(4)]

    @staticmethod
    def _make_bar(master) -> ctk.CTkToplevel:
        bar = ctk.CTkToplevel(master)
        bar.overrideredirect(True)
        try:
            bar.attributes("-topmost", True)
        except Exception:
            pass
        try:
            bar.attributes("-alpha", 0.95)
        except Exception:
            pass
        bar.configure(fg_color=T.ACCENT)
        _make_click_through(bar)
        bar.withdraw()
        return bar

    def move_to(self, widget) -> bool:
        if widget is None:
            self.hide()
            return False
        try:
            if not widget.winfo_exists() or not widget.winfo_ismapped():
                self.hide()
                return False
            widget.update_idletasks()
            x = widget.winfo_rootx() - RING_PADDING
            y = widget.winfo_rooty() - RING_PADDING
            w = widget.winfo_width() + RING_PADDING * 2
            h = widget.winfo_height() + RING_PADDING * 2
        except Exception:
            self.hide()
            return False
        if w <= RING_THICKNESS * 2 or h <= RING_THICKNESS * 2:
            self.hide()
            return False
        top, bottom, left, right = self._bars
        top.geometry(f"{w}x{RING_THICKNESS}+{x}+{y}")
        bottom.geometry(f"{w}x{RING_THICKNESS}+{x}+{y + h - RING_THICKNESS}")
        left.geometry(f"{RING_THICKNESS}x{h}+{x}+{y}")
        right.geometry(f"{RING_THICKNESS}x{h}+{x + w - RING_THICKNESS}+{y}")
        for bar in self._bars:
            bar.deiconify()
        return True

    def hide(self) -> None:
        for bar in self._bars:
            try:
                bar.withdraw()
            except Exception:
                pass

    def destroy(self) -> None:
        for bar in self._bars:
            try:
                bar.destroy()
            except Exception:
                pass


class _DetailCard(_OverlayToplevel):
    """The floating, cursor-chasing explanation card."""

    def __init__(self, master):
        super().__init__(master, click_through=True)
        self.win.configure(fg_color=T.BG_SURFACE)
        outer = ctk.CTkFrame(self.win, fg_color=T.BG_SURFACE, corner_radius=12,
                              border_width=1, border_color=T.ACCENT, width=CARD_WIDTH)
        outer.pack(fill="both", expand=True)
        outer.pack_propagate(False)

        header = ctk.CTkFrame(outer, fg_color="transparent")
        header.pack(fill="x", padx=14, pady=(12, 2))
        self._icon_var = ctk.StringVar()
        ctk.CTkLabel(header, textvariable=self._icon_var,
                     font=ctk.CTkFont(size=18)).pack(side="left", padx=(0, 8))
        self._title_var = ctk.StringVar()
        ctk.CTkLabel(header, textvariable=self._title_var,
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=T.TEXT_HEAD).pack(side="left")

        self._desc_var = ctk.StringVar()
        ctk.CTkLabel(outer, textvariable=self._desc_var, text_color=T.TEXT_MUTED,
                     font=ctk.CTkFont(size=11), wraplength=CARD_WIDTH - 28,
                     justify="left").pack(anchor="w", padx=14, pady=(0, 12))

        self._pos: Optional[Tuple[float, float]] = None

    def set_content(self, icon: str, title: str, description: str) -> None:
        self._icon_var.set(icon)
        self._title_var.set(title)
        self._desc_var.set(description)

    def move_instant(self, x: float, y: float) -> None:
        self._pos = (x, y)
        self.win.geometry(f"+{int(x)}+{int(y)}")

    def ease_toward(self, tx: float, ty: float, factor: float = CARD_EASE) -> None:
        if self._pos is None:
            self._pos = (tx, ty)
        cx, cy = self._pos
        nx, ny = cx + (tx - cx) * factor, cy + (ty - cy) * factor
        self._pos = (nx, ny)
        self.win.geometry(f"+{int(nx)}+{int(ny)}")


class _CursorGlow(_OverlayToplevel):
    """A small soft accent-colored dot that trails the real cursor slightly
    faster than the detail card does (a shorter, tighter chase), for a
    layered depth feel. Rendered as a real circle via `-transparentcolor`
    where available, a plain filled square elsewhere — degraded but not
    broken."""

    def __init__(self, master):
        super().__init__(master, click_through=True)
        d = GLOW_DIAMETER
        transparent = _try_transparent_color(self.win, _TRANSPARENT_KEY)
        bg = _TRANSPARENT_KEY if transparent else T.resolve(T.BG_MAIN)
        self.win.configure(fg_color=bg)
        canvas = tk.Canvas(self.win, width=d, height=d, highlightthickness=0, bg=bg)
        canvas.pack()
        canvas.create_oval(1, 1, d - 1, d - 1, fill=T.resolve(T.ACCENT), outline="")
        self._pos: Optional[Tuple[float, float]] = None

    def ease_toward(self, px: float, py: float, factor: float = GLOW_EASE) -> None:
        d = GLOW_DIAMETER
        tx, ty = px - d / 2, py - d / 2
        if self._pos is None:
            self._pos = (tx, ty)
        cx, cy = self._pos
        nx, ny = cx + (tx - cx) * factor, cy + (ty - cy) * factor
        self._pos = (nx, ny)
        self.win.geometry(f"+{int(nx)}+{int(ny)}")


class _DiscoveredBadge(_OverlayToplevel):
    """A small persistent green checkmark pinned to a widget's corner once
    it's been discovered this session — the redesign's own "visible
    progress" requirement, tracked per-item rather than as a single global
    counter alone."""

    def __init__(self, master):
        super().__init__(master, click_through=True)
        d = BADGE_DIAMETER
        transparent = _try_transparent_color(self.win, _TRANSPARENT_KEY)
        bg = _TRANSPARENT_KEY if transparent else T.resolve(T.BG_MAIN)
        self.win.configure(fg_color=bg)
        canvas = tk.Canvas(self.win, width=d, height=d, highlightthickness=0, bg=bg)
        canvas.pack()
        canvas.create_oval(1, 1, d - 1, d - 1, fill=T.resolve(T.SUCCESS), outline="")
        canvas.create_text(d / 2, d / 2 + 1, text="✓", fill="white",
                            font=("Segoe UI", 9, "bold"))

    def move_to(self, x: float, y: float) -> None:
        self.win.geometry(f"+{int(x)}+{int(y)}")


class _ProgressHud:
    """The persistent, genuinely-clickable "X of Y explored" + Exit Tour
    panel — the redesign's own explicit "not aimless" requirement. Not
    click-through, unlike everything else in this module: its button has to
    actually receive clicks."""

    # Real bug found while reviewing this feature's own demo screenshot: a
    # freshly-constructed CTkToplevel's winfo_width()/winfo_reqwidth() does
    # NOT reflect its real, pack-computed content size until it's gone
    # through a real window-manager configure round-trip -- the same class
    # of "un-rendered placeholder size" issue window_utils.py's own
    # docstring already documents for centering brand-new dialogs (there it
    # measured a stale 200x200; here it was a stale 300, still wrong either
    # way). Confirmed directly: `winfo_width()` returned 300 both
    # immediately after construction AND after an explicit deiconify+
    # update() — positioning against that number pushed "Exit Tour" fully
    # past the real window's right edge, cut off in a real screenshot.
    # Every other dialog in this app sidesteps this exact issue by never
    # relying on natural pack-sizing for a Toplevel in the first place —
    # same fix here: an explicit, deliberately-generous, verified-to-fit
    # geometry instead of a measured one.
    WIDTH = 300
    HEIGHT = 46

    def __init__(self, master, on_exit: Callable[[], None]):
        self.win = ctk.CTkToplevel(master)
        self.win.overrideredirect(True)
        try:
            self.win.attributes("-topmost", True)
        except Exception:
            pass
        self.win.geometry(f"{self.WIDTH}x{self.HEIGHT}")
        self.win.configure(fg_color=T.BG_SURFACE)
        outer = ctk.CTkFrame(self.win, fg_color=T.BG_SURFACE, corner_radius=14,
                              border_width=1, border_color=T.ACCENT)
        outer.pack(fill="both", expand=True)
        row = ctk.CTkFrame(outer, fg_color="transparent")
        row.pack(padx=14, pady=8)
        ctk.CTkLabel(row, text="🔎", font=ctk.CTkFont(size=14)).pack(side="left", padx=(0, 8))
        self._text_var = ctk.StringVar(value="0 of 0 explored")
        ctk.CTkLabel(row, textvariable=self._text_var, text_color=T.TEXT_HEAD,
                     font=ctk.CTkFont(size=11, weight="bold")).pack(side="left", padx=(0, 12))
        self.exit_btn = ctk.CTkButton(
            row, text="Exit Tour", width=84, height=26, corner_radius=8,
            fg_color=T.BG_INNER, hover_color=T.BG_BORDER, border_width=1,
            border_color=T.BG_BORDER, text_color=T.ACCENT_TEXT,
            font=ctk.CTkFont(size=10, weight="bold"), command=on_exit)
        self.exit_btn.pack(side="left")
        self.win.withdraw()

    def set_progress(self, discovered: int, total: int) -> None:
        self._text_var.set(f"{discovered} of {total} explored")

    def position_near(self, main_window) -> None:
        # A second real bug in the same fix: CustomTkinter's own
        # `.geometry()` override silently multiplies just the WxH
        # component by its per-monitor DPI scale (e.g. 1.25 at 125%
        # Windows scaling) but leaves any +x+y position component
        # unscaled -- the exact same characteristic `window_utils.py`
        # already documents for dialog centering. Using the logical WIDTH
        # constant directly in this offset math (as a first version of
        # this fix did) left the HUD's *real*, physical 375px-wide window
        # extending ~50px past the real window's right edge even though
        # its actual button/text content looked fine -- confirmed via
        # direct winfo_rootx()/winfo_width() measurement, not assumed.
        # `_apply_window_scaling` is the same real, deterministic escape
        # hatch `window_utils._real_dimensions` already uses for this.
        main_window.update_idletasks()
        scale = getattr(self.win, "_apply_window_scaling", None)
        real_width = scale(self.WIDTH) if callable(scale) else self.WIDTH
        x = main_window.winfo_rootx() + main_window.winfo_width() - real_width - 24
        y = main_window.winfo_rooty() + 74
        self.win.geometry(f"{self.WIDTH}x{self.HEIGHT}+{max(0, x)}+{max(0, y)}")

    def show(self) -> None:
        try:
            self.win.deiconify()
        except Exception:
            pass

    def hide(self) -> None:
        try:
            self.win.withdraw()
        except Exception:
            pass

    def destroy(self) -> None:
        try:
            self.win.destroy()
        except Exception:
            pass


class TourMode:
    """Owns the whole hover-to-discover experience for one MainWindow.
    Constructed once (`MainWindow.__init__` creates `self.tour_mode`) and
    reused across repeated enable()/disable() cycles."""

    def __init__(self, main_window):
        self.main_window = main_window
        self.is_active = False
        self._discovered: Set[str] = set()
        self._total = 0
        self._active_id: Optional[str] = None
        self._bindings: Dict[str, Tuple[object, str, str]] = {}
        self._badges: Dict[str, _DiscoveredBadge] = {}
        self._escape_bind_id: Optional[str] = None
        self._hide_after_id = None
        self._follow_after_id = None
        self._fade_after_id = None
        self._badge_refresh_after_id = None
        self._current_alpha = 0.0
        self._ring: Optional[_SpotlightRing] = None
        self._card: Optional[_DetailCard] = None
        self._glow: Optional[_CursorGlow] = None
        self._hud: Optional[_ProgressHud] = None

    # ── public state ────────────────────────────────────────────────────
    @property
    def discovered_count(self) -> int:
        return len(self._discovered)

    @property
    def total_count(self) -> int:
        return self._total

    # ── lifecycle ────────────────────────────────────────────────────────
    def toggle(self) -> None:
        if self.is_active:
            self.disable()
        else:
            self.enable()

    def enable(self) -> None:
        if self.is_active:
            return
        mw = self.main_window
        self._ring = _SpotlightRing(mw)
        self._card = _DetailCard(mw)
        self._glow = _CursorGlow(mw)
        self._hud = _ProgressHud(mw, on_exit=self.disable)

        self._discovered = set()
        self._active_id = None
        self._current_alpha = 0.0
        self._bindings = {}
        for item in DISCOVERABLE_ITEMS:
            widget = item["getter"](mw)
            if widget is None:
                continue
            target = _hover_target(widget)
            enter_id = target.bind(
                "<Enter>", lambda _e, iid=item["id"]: self._on_enter(iid), add="+")
            leave_id = target.bind(
                "<Leave>", lambda _e, iid=item["id"]: self._on_leave(iid), add="+")
            self._bindings[item["id"]] = (target, enter_id, leave_id)
        self._total = len(self._bindings)

        self._escape_bind_id = mw.bind("<Escape>", lambda _e: self.disable(), add="+")

        self._hud.set_progress(0, self._total)
        self._hud.position_near(mw)
        self._hud.show()

        header_btn = getattr(mw, "header_tour_btn", None)
        if header_btn is not None:
            try:
                header_btn.configure(fg_color=T.ACCENT, text_color=T.TEXT_HEAD)
            except Exception:
                pass

        self.is_active = True
        self._refresh_badges()

    def disable(self) -> None:
        if not self.is_active:
            return
        mw = self.main_window
        self._cancel_all_after()

        for target, enter_id, leave_id in self._bindings.values():
            try:
                target.unbind("<Enter>", enter_id)
                target.unbind("<Leave>", leave_id)
            except Exception:
                pass
        self._bindings = {}

        if self._escape_bind_id is not None:
            try:
                mw.unbind("<Escape>", self._escape_bind_id)
            except Exception:
                pass
            self._escape_bind_id = None

        for badge in self._badges.values():
            badge.destroy()
        self._badges = {}

        for overlay in (self._ring, self._card, self._glow, self._hud):
            if overlay is not None:
                overlay.destroy()
        self._ring = self._card = self._glow = self._hud = None

        header_btn = getattr(mw, "header_tour_btn", None)
        if header_btn is not None:
            try:
                header_btn.configure(fg_color=T.BADGE_BG, text_color=T.ACCENT_TEXT)
            except Exception:
                pass

        self._active_id = None
        self.is_active = False

    def _cancel_all_after(self) -> None:
        mw = self.main_window
        for attr in ("_hide_after_id", "_follow_after_id", "_fade_after_id",
                     "_badge_refresh_after_id"):
            after_id = getattr(self, attr)
            if after_id is not None:
                try:
                    mw.after_cancel(after_id)
                except Exception:
                    pass
                setattr(self, attr, None)

    def _item(self, item_id: str) -> Optional[DiscoverableItem]:
        for item in DISCOVERABLE_ITEMS:
            if item["id"] == item_id:
                return item
        return None

    # ── hover handlers (called by real <Enter>/<Leave> bindings, and
    # directly by tests -- same code path either way) ─────────────────────
    def _on_enter(self, item_id: str) -> None:
        if not self.is_active:
            return
        mw = self.main_window
        if self._hide_after_id is not None:
            try:
                mw.after_cancel(self._hide_after_id)
            except Exception:
                pass
            self._hide_after_id = None

        item = self._item(item_id)
        if item is None:
            return
        widget = item["getter"](mw)
        if widget is None:
            return

        if item_id not in self._discovered:
            self._discovered.add(item_id)
            self._hud.set_progress(len(self._discovered), self._total)
            self._show_badge(item_id, widget)

        if self._active_id != item_id:
            self._active_id = item_id
            self._card.set_content(item["icon"], item["title"], item["description"])
            self._ring.move_to(widget)
            self._card.show()
            self._glow.show()
            self._fade_to(0.97)
            self._start_follow()

    def _on_leave(self, item_id: str) -> None:
        if not self.is_active:
            return
        mw = self.main_window

        def check_leave() -> None:
            self._hide_after_id = None
            if self._active_id == item_id:
                self._active_id = None
                self._ring.hide()
                self._stop_follow()
                card, glow = self._card, self._glow
                self._fade_to(0.0, on_done=lambda: (card.hide(), glow.hide()))

        self._hide_after_id = mw.after(HIDE_DELAY_MS, check_leave)

    # ── discovery badges ─────────────────────────────────────────────────
    def _show_badge(self, item_id: str, widget) -> None:
        badge = self._badges.get(item_id)
        if badge is None:
            badge = _DiscoveredBadge(self.main_window)
            self._badges[item_id] = badge
        self._position_badge(badge, widget)
        badge.show()

    @staticmethod
    def _position_badge(badge: _DiscoveredBadge, widget) -> None:
        try:
            x = widget.winfo_rootx() + widget.winfo_width() - 10
            y = widget.winfo_rooty() - 8
            badge.move_to(x, y)
        except Exception:
            pass

    def _refresh_badges(self) -> None:
        if not self.is_active:
            return
        mw = self.main_window
        for item_id, badge in self._badges.items():
            item = self._item(item_id)
            widget = item["getter"](mw) if item is not None else None
            try:
                mapped = widget is not None and widget.winfo_exists() and widget.winfo_ismapped()
            except Exception:
                mapped = False
            if mapped:
                self._position_badge(badge, widget)
                badge.show()
            else:
                badge.hide()
        self._badge_refresh_after_id = mw.after(BADGE_REFRESH_MS, self._refresh_badges)

    # ── cursor-follow animation ──────────────────────────────────────────
    def _start_follow(self) -> None:
        if self._follow_after_id is not None:
            return
        self._follow_tick()

    def _stop_follow(self) -> None:
        if self._follow_after_id is not None:
            try:
                self.main_window.after_cancel(self._follow_after_id)
            except Exception:
                pass
            self._follow_after_id = None

    def _follow_tick(self) -> None:
        if self._active_id is None or not self.is_active:
            self._follow_after_id = None
            return
        mw = self.main_window
        px, py = mw.winfo_pointerx(), mw.winfo_pointery()
        screen_w = mw.winfo_screenwidth()
        screen_h = _work_area_bottom(mw.winfo_screenheight())
        tx = min(px + CARD_OFFSET_X, max(0, screen_w - CARD_WIDTH - 8))
        ty = min(py + CARD_OFFSET_Y, max(0, screen_h - CARD_HEIGHT_ESTIMATE - 8))
        self._card.ease_toward(tx, ty)
        self._glow.ease_toward(px, py)
        self._follow_after_id = mw.after(FOLLOW_TICK_MS, self._follow_tick)

    # ── fade in/out ───────────────────────────────────────────────────────
    def _fade_to(self, target: float, on_done: Optional[Callable[[], None]] = None) -> None:
        if self._fade_after_id is not None:
            try:
                self.main_window.after_cancel(self._fade_after_id)
            except Exception:
                pass
            self._fade_after_id = None
        start = self._current_alpha
        steps = FADE_STEPS

        def step(i: int = 0) -> None:
            alpha = start + (target - start) * (i / steps)
            self._current_alpha = alpha
            self._card.set_alpha(alpha)
            self._glow.set_alpha(alpha * 0.9)
            if i < steps:
                self._fade_after_id = self.main_window.after(
                    FADE_STEP_MS, lambda: step(i + 1))
            else:
                self._fade_after_id = None
                if on_done is not None:
                    on_done()

        step()


def install_tour_mode(main_window) -> TourMode:
    return TourMode(main_window)
