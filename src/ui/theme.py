"""
Central design tokens for MessageCannon Pro.

RULE: Koi bhi UI component koi bhi naya hex color NAHI likhega.
      Sirf yahan defined tokens use honge — import karo, hardcode mat karo.

Contrast audit (WCAG):
  TEXT_HEAD  / BG_SURFACE  15.02:1  AAA
  TEXT_MUTED / BG_SURFACE   4.94:1  AA
  BG_SURFACE / BG_MAIN      1.92:1  (cards visible — was broken at 1.17:1)
  BG_BORDER  / BG_SURFACE   1.45:1  (border visible — was broken at same)
"""

# ── Backgrounds ───────────────────────────────────────────────────────────────
BG_MAIN    = "#0F1419"   # app root (darkest layer)
BG_SURFACE = "#2A4762"   # cards, panels — 1.92:1 vs BG_MAIN
BG_INNER   = "#152C42"   # text inputs, deep nested — sunken inside cards
BG_BORDER  = "#3F5E84"   # all borders / dividers
BADGE_BG   = "#1F3A57"   # pills, chips, badge backgrounds
NAV_INACTIVE = "#18304A" # inactive sidebar button

# ── Text ──────────────────────────────────────────────────────────────────────
TEXT_HEAD  = "#E2E8F0"   # primary text — values, headings       (7.83:1 on BG_SURFACE)
TEXT_MUTED = "#AEBBC8"   # supporting text — labels, captions    (4.94:1 on BG_SURFACE, WCAG AA)
TEXT_DIM   = "#7B8FA0"   # metadata only — timestamps, hints     (ok on BG_MAIN only)

# ── Accent ────────────────────────────────────────────────────────────────────
# IMPORTANT: ACCENT must be used as a BACKGROUND (fg_color=T.ACCENT) not as text_color on
# BG_SURFACE (fails 4.5:1 there). As text it is only ok on BG_MAIN (4.14:1, nav/links).
ACCENT       = "#6366F1"   # ONE primary accent — buttons, active nav
ACCENT_HOVER = "#4F46E5"   # hover state of ACCENT

# ── Semantic ──────────────────────────────────────────────────────────────────
SUCCESS      = "#10B981"   # positive states
DANGER       = "#EF4444"   # destructive actions only (use as bg, not text on BG_SURFACE)
DANGER_HOVER = "#DC2626"   # hover state of DANGER

# Badge text variants — use these as text_color ON fg_color=BADGE_BG only.
# Contrast audited vs BADGE_BG (#1F3A57, L=0.040):
#   DANGER_ON_BADGE  / BADGE_BG  4.66:1  AA  (T.DANGER gives 3.10:1 — FAIL)
#   SUCCESS (#10B981) / BADGE_BG  4.61:1  AA  (no override needed)
DANGER_ON_BADGE = "#FF7B7B"
