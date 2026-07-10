"""
Central design tokens for MessageCannon Pro.

RULE: Koi bhi UI component koi bhi naya hex color NAHI likhega.
      Sirf yahan defined tokens use honge — import karo, hardcode mat karo.

Every token is a (light, dark) tuple. CustomTkinter widgets (CTkFrame,
CTkButton, CTkLabel, ...) accept these tuples directly for any color
parameter (fg_color, text_color, border_color, ...) and resolve + auto-update
them on ctk.set_appearance_mode() with zero extra code — that's native CTk
behavior, not something this module implements.

Only plain tkinter widgets (tk.Frame, tk.Button — a handful of spots that
predate/bypass CTk) can't consume a tuple directly. For those, call
resolve(T.SOME_TOKEN) to get the single hex value for the current mode, and
re-apply it on theme toggle (see MainWindow._sync_theme_overrides).

Contrast audit (WCAG), dark mode (original):
  TEXT_HEAD  / BG_SURFACE  15.02:1  AAA
  TEXT_MUTED / BG_SURFACE   4.94:1  AA
  BG_SURFACE / BG_MAIN      1.92:1  (cards visible — was broken at 1.17:1)
  BG_BORDER  / BG_SURFACE   1.45:1  (border visible — was broken at same)

Contrast audit, light mode (new):
  TEXT_HEAD  / BG_SURFACE  18.1:1   AAA  (#12161C on #FFFFFF)
  TEXT_MUTED / BG_SURFACE   5.4:1   AA   (#5B6570 on #FFFFFF)
  BG_SURFACE / BG_MAIN      ~1.05:1 (white card vs near-white page — relies on
                                      BG_BORDER for separation, matching the
                                      flat "platinum editorial" reference look)
  BG_BORDER  / BG_SURFACE   1.12:1  (visible hairline, intentionally subtle)
  DANGER_ON_BADGE / BADGE_BG 5.9:1  AA  (#B91C1C on #EEF1F6 — the dark-tuned
                                          bright red #FF7B7B fails on a light
                                          chip background, needs its own value)
"""

import customtkinter as ctk

# ── Backgrounds ───────────────────────────────────────────────────────────────
#                token       = (   light   ,    dark    )
BG_MAIN      = ("#F4F6FA", "#0F1419")   # app root
BG_SURFACE   = ("#FFFFFF", "#2A4762")   # cards, panels
BG_INNER     = ("#F1F3F7", "#152C42")   # text inputs, deep nested — sunken inside cards
BG_BORDER    = ("#E2E5EA", "#3F5E84")   # all borders / dividers
BADGE_BG     = ("#EEF1F6", "#1F3A57")   # pills, chips, badge backgrounds
NAV_INACTIVE = ("#F1F3F7", "#18304A")   # inactive sidebar button

# ── Text ──────────────────────────────────────────────────────────────────────
TEXT_HEAD  = ("#12161C", "#E2E8F0")   # primary text — values, headings
TEXT_MUTED = ("#5B6570", "#AEBBC8")   # supporting text — labels, captions
TEXT_DIM   = ("#78828E", "#7B8FA0")   # metadata only — timestamps, hints

# ── Accent ────────────────────────────────────────────────────────────────────
# IMPORTANT: ACCENT must be used as a BACKGROUND (fg_color=T.ACCENT) not as text_color on
# BG_SURFACE (fails 4.5:1 there in dark mode). As text it is only ok on BG_MAIN (nav/links).
# Same accent in both modes — brand consistency, already reads fine on white.
ACCENT       = ("#6366F1", "#6366F1")   # ONE primary accent — buttons, active nav
ACCENT_HOVER = ("#4F46E5", "#4F46E5")   # hover state of ACCENT

# ── Semantic ──────────────────────────────────────────────────────────────────
SUCCESS      = ("#10B981", "#10B981")   # positive states
DANGER       = ("#EF4444", "#EF4444")   # destructive actions only (use as bg, not text on BG_SURFACE)
DANGER_HOVER = ("#DC2626", "#DC2626")   # hover state of DANGER

# Badge text variants — use these as text_color ON fg_color=BADGE_BG only.
DANGER_ON_BADGE = ("#B91C1C", "#FF7B7B")


def resolve(token):
    """Pick the single hex value from a (light, dark) token for the current
    CTk appearance mode. Only needed for raw tk.* widgets — CTk widgets
    accept the tuple directly and resolve it themselves."""
    if not isinstance(token, tuple):
        return token
    light, dark = token
    return light if ctk.get_appearance_mode() == "Light" else dark
