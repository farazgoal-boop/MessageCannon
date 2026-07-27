"""
Central design tokens for MessageCannon Pro.

RULE: Koi bhi UI component koi bhi naya hex color NAHI likhega.
      Sirf yahan defined tokens use honge — import karo, hardcode mat karo.

Three named palettes: "dark" (default), "light", "warm_ivory". Access is via
plain attributes exactly as before — `T.BG_MAIN` etc. — powered by a
module-level __getattr__ (PEP 562) so no call site anywhere in the app needs
to change.

How resolution works, and why there are two different mechanisms:
- Dark <-> Light switching uses CustomTkinter's OWN native mechanism: each
  token is a real (light_hex, dark_hex) tuple, CTk widgets accept tuples
  directly and auto-resolve + auto-update on ctk.set_appearance_mode() with
  zero extra code. This is fast (no rebuild) and already proven solid.
- Warm Ivory is a genuine third state that CTk's binary appearance mode has
  no concept of. There is no way to make already-constructed CTk widgets
  pick up a 3rd palette after the fact (a widget stores whichever (light,
  dark) tuple object it was given at construction and never re-reads
  theme.py). So entering/leaving Warm Ivory tells __getattr__ to hand out
  (warm_hex, warm_hex) — an identical pair regardless of which half CTk
  resolves — and MainWindow does a full UI rebuild (_rebuild_ui_for_theme)
  so every widget is freshly constructed against the new palette. This is
  a deliberate, documented tradeoff: a brief rebuild on the rare "switch to/
  from Warm Ivory" action, in exchange for not needing a fragile app-wide
  widget registry just to support a third state.

Contrast audit (WCAG), dark/light (original, unchanged):
  TEXT_HEAD  / BG_SURFACE  dark 15.02:1 AAA   light 18.1:1 AAA
  TEXT_MUTED / BG_SURFACE  dark  4.94:1 AA    light  5.4:1 AA

Contrast audit, warm_ivory (new):
  TEXT_HEAD  (#2B2418) / BG_SURFACE (#FFFDF8)   15.9:1  AAA
  TEXT_MUTED (#7A6F5C) / BG_SURFACE (#FFFDF8)    4.6:1  AA
  DANGER_ON_BADGE (#B91C1C) / BADGE_BG (#F3EAD8) 5.7:1  AA

Contrast audit, ACCENT_TEXT (added Item 27, Final Premium Polish Pass): plain
ACCENT measured as low as 2.16:1 (dark mode) as a *text* color on
BG_SURFACE/BG_INNER/BADGE_BG — a real WCAG fail, exactly the scenario this
file's own Design System rule already warned about ("use ACCENT as fg_color
only, NOT text_color on cards"). ACCENT_TEXT passes AA against all three of
those backgrounds, in all three palettes:
  dark:  A5B4FC / BG_SURFACE #2A4762  4.84:1   / BG_INNER #152C42  7.16:1   / BADGE_BG #1F3A57  5.85:1
  light: 4F46E5 / BG_SURFACE #FFFFFF  6.29:1   / BG_INNER #F1F3F7  5.66:1   / BADGE_BG #EEF1F6  5.55:1
  warm:  94530F / BG_SURFACE #FFFDF8  5.90:1   / BG_INNER #F3EAD8  5.02:1   / BADGE_BG #F3EAD8  5.02:1
"""

import customtkinter as ctk

_PALETTE_NAMES = ("dark", "light", "warm_ivory")
_current_palette = "dark"


def set_palette(name: str) -> None:
    global _current_palette
    if name not in _PALETTE_NAMES:
        raise ValueError(f"Unknown palette {name!r}, expected one of {_PALETTE_NAMES}")
    _current_palette = name


def get_palette() -> str:
    return _current_palette


# ── Dark / Light tokens — (light, dark) tuples, CTk-native resolution ─────────
_TOKENS = {
    "BG_MAIN":          ("#F4F6FA", "#0F1419"),
    "BG_SURFACE":       ("#FFFFFF", "#2A4762"),
    "BG_INNER":         ("#F1F3F7", "#152C42"),
    "BG_BORDER":        ("#E2E5EA", "#3F5E84"),
    "BADGE_BG":         ("#EEF1F6", "#1F3A57"),
    "NAV_INACTIVE":     ("#F1F3F7", "#18304A"),
    "TEXT_HEAD":        ("#12161C", "#E2E8F0"),
    "TEXT_MUTED":       ("#5B6570", "#AEBBC8"),
    "TEXT_DIM":         ("#78828E", "#7B8FA0"),
    "ACCENT":           ("#6366F1", "#6366F1"),
    "ACCENT_HOVER":     ("#4F46E5", "#4F46E5"),
    "ACCENT_TEXT":      ("#4F46E5", "#A5B4FC"),
    "SUCCESS":          ("#10B981", "#10B981"),
    "SUCCESS_HOVER":    ("#059669", "#059669"),
    "DANGER":           ("#EF4444", "#EF4444"),
    "DANGER_HOVER":     ("#DC2626", "#DC2626"),
    "DANGER_ON_BADGE":  ("#B91C1C", "#FF7B7B"),
}

# ── Warm Ivory — single hex per token (see module docstring for why) ──────────
_WARM_IVORY = {
    "BG_MAIN":          "#F5EEDD",
    "BG_SURFACE":       "#FFFDF8",
    "BG_INNER":         "#F3EAD8",
    "BG_BORDER":        "#E6D9BE",
    "BADGE_BG":         "#F3EAD8",
    "NAV_INACTIVE":     "#F3EAD8",
    "TEXT_HEAD":        "#2B2418",
    "TEXT_MUTED":       "#7A6F5C",
    "TEXT_DIM":         "#948968",
    "ACCENT":           "#B5651D",
    "ACCENT_HOVER":     "#94530F",
    "ACCENT_TEXT":      "#94530F",
    "SUCCESS":          "#0F8A5F",
    "SUCCESS_HOVER":    "#0D7551",
    "DANGER":           "#C0392B",
    "DANGER_HOVER":     "#A6301F",
    "DANGER_ON_BADGE":  "#B91C1C",
}


def __getattr__(name: str):
    if name in _TOKENS:
        if _current_palette == "warm_ivory":
            value = _WARM_IVORY[name]
            return (value, value)
        return _TOKENS[name]
    raise AttributeError(f"module 'theme' has no attribute {name!r}")


def resolve(token):
    """Pick the single hex value from a (light, dark) token for the current
    CTk appearance mode. Only needed for raw tk.* widgets — CTk widgets
    accept the tuple directly and resolve it themselves."""
    if not isinstance(token, tuple):
        return token
    light, dark = token
    return light if ctk.get_appearance_mode() == "Light" else dark


def bg_main_for_mode(mode: str) -> str:
    """BG_MAIN's exact hex for a specific *target* mode ("Dark"/"Light"/
    "Warm Ivory"/"System"), independent of whatever palette is currently
    active — used by the theme-switch transition overlay (Item 14 of the
    Live Testing Findings pass, Round 2), which needs to know the
    DESTINATION background color before the actual switch happens, not the
    current one. Kept here (not hardcoded in main_window.py) so this stays
    the single source of truth for every hex value, per this file's own
    Design System rule."""
    if mode == "Warm Ivory":
        return _WARM_IVORY["BG_MAIN"]
    light, dark = _TOKENS["BG_MAIN"]
    return dark if mode == "Dark" else light
