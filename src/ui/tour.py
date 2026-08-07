"""Reusable, re-triggerable guided product tour ("Take a Tour" / "?" button).

Item 39 (Guided Tour + User Manual pass). Two real, permanent entry points —
the header's own "?" icon next to the Settings gear, and a "Take a Tour"
button in Settings' System Experience card, right next to the pre-existing
"Re-run Setup Wizard" button since both are on-demand, re-runnable help
actions — open a sequence of cards walking through every major part of the
app. Unlike the Setup Wizard (Phase 1), this is not gated by any "seen
before" flag: every open starts fresh at step 1, by construction (no
persisted state at all), so it works identically the first time and the
hundredth time.

Spotlight mechanic, chosen deliberately over a plain floating-card slideshow:
CustomTkinter/Tk has no per-widget alpha or screen-dim capability — the same
structural limitation this app has already hit and documented for the
signature view-transition animation and the sidebar's own gradient accent
bar (see CLAUDE.md). A true dimmed-background spotlight would need
screen-capture compositing, already ruled out elsewhere in this app as
fragile/platform-specific for the same reason. Instead, four thin, real,
positioned `CTkToplevel` bars (`overrideredirect` + `-topmost`, the same
technique already proven by toast.py/tooltip.py) are drawn to form a
rectangular accent-colored ring directly around the real target widget's own
on-screen bounding box — genuinely tied to the real interface, not a
generic illustration, while staying within what this stack can reliably do.

Each step also carries a large glyph "thumbnail" (reusing the same emoji/
glyph icon language already used throughout this app's own UI, e.g. the
sidebar nav icons) rather than an embedded screenshot — this sandbox's own
screenshot capture has already been shown, more than once, to be unreliable
and to risk capturing unrelated windows on the developer's live desktop (see
CLAUDE.md's Final Completion Pass Item 5); a real screenshot for this tour
is exactly the kind of thing that needs the developer's own machine, not
fabricated here.
"""

from __future__ import annotations

from typing import Callable, List, Optional, TypedDict

import customtkinter as ctk

from . import theme as T
from .window_utils import center_on_parent

RING_THICKNESS = 3
RING_PADDING = 5


class TourStep(TypedDict):
    id: str
    icon: str
    title: str
    body: str
    view: Optional[str]
    target: Optional[Callable[[object], Optional[object]]]


TOUR_STEPS: List[TourStep] = [
    {
        "id": "welcome",
        "icon": "👋",
        "title": "Welcome to MessageCannon Pro",
        "body": ("A quick tour of every major part of the app — takes about a "
                  "minute. You can re-run this anytime from the \"?\" button "
                  "next to Settings."),
        "view": None,
        "target": None,
    },
    {
        "id": "campaigns",
        "icon": "⊞",
        "title": "Campaigns Dashboard",
        "body": ("Your home base — recent campaigns, real send/delivery "
                  "stats, and a 7-day sending trend at a glance."),
        "view": "Campaigns",
        "target": lambda mw: mw.sidebar_buttons.get("Campaigns"),
    },
    {
        "id": "contacts",
        "icon": "☰",
        "title": "Import Contacts",
        "body": ("Bring in contacts from a CSV or Excel file with a real "
                  "review step first — duplicates, bad phone numbers, and "
                  "bad emails are flagged with a clear reason before "
                  "anything is saved."),
        "view": "Contacts",
        "target": lambda mw: mw.sidebar_buttons.get("Contacts"),
    },
    {
        "id": "compose",
        "icon": "✉",
        "title": "Compose — Email & WhatsApp",
        "body": ("Write once, personalize per contact. \"Generate with AI\" "
                  "drafts real copy and true per-recipient variations from "
                  "your own imported data, using your own AI key."),
        "view": "Compose",
        "target": lambda mw: mw.sidebar_buttons.get("Compose"),
    },
    {
        "id": "cards",
        "icon": "❏",
        "title": "Card Creator",
        "body": ("Design a real, standalone marketing card — image, price, "
                  "discount, and a working Buy Now button — then send it "
                  "for real or drop it straight into Compose."),
        "view": "Cards",
        "target": lambda mw: mw.sidebar_buttons.get("Cards"),
    },
    {
        "id": "history",
        "icon": "◈",
        "title": "Delivery & Bounce Tracking",
        "body": ("After a campaign sends, MessageCannon can check your real "
                  "inbox for bounces and reconcile them here — an honest "
                  "\"Sent / Bounced / Delivered (assumed)\" breakdown, not "
                  "a guess."),
        "view": "History",
        "target": lambda mw: mw.sidebar_buttons.get("History"),
    },
    {
        "id": "settings",
        "icon": "⚙",
        "title": "Settings & License",
        "body": ("Connect your email/WhatsApp, set safe sending limits, "
                  "pick your theme, and manage license activation — all "
                  "local to this device."),
        "view": "Settings",
        "target": lambda mw: mw.sidebar_buttons.get("Settings"),
    },
    {
        "id": "updates",
        "icon": "⬆",
        "title": "Automatic Updates",
        "body": ("When a new version is published, a badge appears right "
                  "here in the sidebar — one click downloads and installs "
                  "it, no manual download needed."),
        "view": None,
        "target": lambda mw: getattr(mw, "_update_badge_slot", None),
    },
    {
        "id": "done",
        "icon": "🎉",
        "title": "You're all set",
        "body": "That's the full tour. Come back to it anytime with this \"?\" button.",
        "view": None,
        "target": lambda mw: getattr(mw, "header_tour_btn", None),
    },
]


class _SpotlightRing:
    """Four thin, always-on-top bars forming a rectangular accent-colored
    outline around a target widget's real screen bounds. `move_to(widget)`
    repositions and shows them; `None` (or an unmapped/destroyed widget)
    hides them instead of guessing at a position."""

    def __init__(self, master: ctk.CTkToplevel):
        self._bars = [self._make_bar(master) for _ in range(4)]

    @staticmethod
    def _make_bar(master: ctk.CTkToplevel) -> ctk.CTkToplevel:
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
        bar.withdraw()
        return bar

    def move_to(self, widget) -> bool:
        """Positions the ring around `widget`'s real, current screen bounds.
        Returns True if it could (widget real, exists, and mapped), False
        if it hid the ring instead (no honest position to show)."""
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


class GuidedTourDialog(ctk.CTkToplevel):
    def __init__(self, main_window):
        super().__init__(main_window)
        self.main_window = main_window
        self._original_view = getattr(main_window, "_active_view", None)
        self._step_index = 0

        self.title("Guided Tour")
        center_on_parent(self, 440, 300, main_window)
        self.resizable(False, False)
        self.transient(main_window)
        self.grab_set()
        self.configure(fg_color=T.BG_MAIN)
        self.protocol("WM_DELETE_WINDOW", self._finish)
        self.bind("<Escape>", lambda _e: self._finish())
        self.bind("<Right>", lambda _e: self._go_next())
        self.bind("<Left>", lambda _e: self._go_back())

        self._ring = _SpotlightRing(self)

        self.grid_columnconfigure(0, weight=1)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, padx=22, pady=(20, 6), sticky="ew")
        header.grid_columnconfigure(1, weight=1)

        self._icon_var = ctk.StringVar()
        ctk.CTkLabel(header, textvariable=self._icon_var,
                     font=ctk.CTkFont(size=30)).grid(row=0, column=0, rowspan=2, padx=(0, 14))

        self._title_var = ctk.StringVar()
        ctk.CTkLabel(header, textvariable=self._title_var,
                     font=ctk.CTkFont(size=17, weight="bold"),
                     text_color=T.TEXT_HEAD, anchor="w", justify="left",
                     wraplength=270).grid(row=0, column=1, sticky="w")

        self._progress_var = ctk.StringVar()
        ctk.CTkLabel(header, textvariable=self._progress_var,
                     text_color=T.TEXT_MUTED, font=ctk.CTkFont(size=11),
                     anchor="w").grid(row=1, column=1, sticky="w")

        body_card = ctk.CTkFrame(self, fg_color=T.BG_SURFACE, corner_radius=12,
                                  border_width=1, border_color=T.BG_BORDER)
        body_card.grid(row=1, column=0, padx=22, pady=(4, 14), sticky="ew")
        self._body_var = ctk.StringVar()
        ctk.CTkLabel(body_card, textvariable=self._body_var,
                     text_color=T.TEXT_MUTED, font=ctk.CTkFont(size=12),
                     wraplength=370, justify="left").pack(
            anchor="w", padx=16, pady=14)

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=2, column=0, padx=22, pady=(0, 18), sticky="ew")
        footer.grid_columnconfigure(1, weight=1)

        ctk.CTkButton(footer, text="Skip", width=70, fg_color="transparent",
                      hover_color=T.BADGE_BG, text_color=T.TEXT_MUTED,
                      command=self._finish).grid(row=0, column=0, sticky="w")

        self._back_btn = ctk.CTkButton(
            footer, text="←  Back", width=90, fg_color=T.BG_INNER,
            hover_color=T.BG_BORDER, border_width=1, border_color=T.BG_BORDER,
            text_color=T.ACCENT_TEXT, command=self._go_back)
        self._back_btn.grid(row=0, column=2, sticky="e", padx=(0, 8))

        self._next_btn = ctk.CTkButton(
            footer, text="Next  →", width=90, fg_color=T.ACCENT,
            hover_color=T.ACCENT_HOVER, text_color=T.TEXT_HEAD,
            command=self._go_next)
        self._next_btn.grid(row=0, column=3, sticky="e")

        self._render_step()

    def _render_step(self) -> None:
        step = TOUR_STEPS[self._step_index]
        if step["view"] is not None:
            self.main_window._show_view(step["view"])
        target = step["target"](self.main_window) if step["target"] else None
        self._ring.move_to(target)

        self._icon_var.set(step["icon"])
        self._title_var.set(step["title"])
        self._body_var.set(step["body"])
        self._progress_var.set(f"Step {self._step_index + 1} of {len(TOUR_STEPS)}")
        self._back_btn.configure(state="normal" if self._step_index > 0 else "disabled")
        is_last = self._step_index == len(TOUR_STEPS) - 1
        self._next_btn.configure(text="Finish" if is_last else "Next  →",
                                  command=self._finish if is_last else self._go_next)

    def _go_next(self) -> None:
        if self._step_index < len(TOUR_STEPS) - 1:
            self._step_index += 1
            self._render_step()

    def _go_back(self) -> None:
        if self._step_index > 0:
            self._step_index -= 1
            self._render_step()

    def _finish(self) -> None:
        self._ring.destroy()
        if self._original_view and self._original_view != self.main_window._active_view:
            try:
                self.main_window._show_view(self._original_view)
            except Exception:
                pass
        if getattr(self.main_window, "_tour_dialog", None) is self:
            self.main_window._tour_dialog = None
        try:
            self.destroy()
        except Exception:
            pass


def start_guided_tour(main_window) -> GuidedTourDialog:
    """Opens the guided tour, always restarting at step 1 — if one is
    already open (e.g. the user clicks "Take a Tour" again mid-tour), it is
    torn down first rather than left running alongside a second copy."""
    existing = getattr(main_window, "_tour_dialog", None)
    if existing is not None:
        try:
            existing._finish()
        except Exception:
            pass
    dialog = GuidedTourDialog(main_window)
    main_window._tour_dialog = dialog
    return dialog
