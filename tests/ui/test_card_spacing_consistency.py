"""Item 28 of the Final Premium Polish Pass: force consistent card/section
padding and vertical rhythm app-wide.

Method: extracted every T.BG_SURFACE card container across `main_window.py`
and `card_creator_tab.py` programmatically (a small scratch script capturing
each card's `corner_radius`, its first-child title CTkLabel's `font`/`padx`/
`pady`), rather than eyeballing individual screens, then compared like-tier
elements against each other.

Real, confirmed inconsistencies found and fixed:

1. **Compose's 3 Email-panel right-column cards** ("SMTP connection",
   "Recipients", "Live preview") used `font=ctk.CTkFont(size=13, ...)` and
   `pady=(14, ...)` — while their own direct structural counterpart, the
   WhatsApp panel's "Preview" card (same row/column position, same Compose
   screen, same conceptual role for the other channel), and every other
   major card app-wide, use `size=15`/`pady=(16, ...)`. Normalized all 3 to
   match — including the SMTP status chip on the same grid row as "SMTP
   connection", so the two don't misalign now that the title's own pady
   changed.
2. **"Delivery Rate" card** title used `size=14` — the sole size-14 title
   app-wide (every other major card title is size=15). Fixed the font size
   only; `pady=14` (shared with this row's 3 other elements: the badge, the
   progress bar, the rate number) was deliberately left alone since this
   card is a genuinely different, single-row layout, not the title-block
   layout the size=15/pady=(16,...) convention otherwise implies. **This
   card lives inside `_build_reports_view`** — already found, in Item 26, to
   be unreachable dead code (never called from `_create_ui` or anywhere
   else). The fix is harmless and correct if that view is ever wired in
   later, but — same as Item 26's own finding — is not a live-app fix;
   verified at the source level only, not against a real running widget.
3. **History's hero card** used `padx=18` (title and subtitle both) where
   every sibling hero (Campaigns home, Contacts, Reports & Analytics) uses
   `padx=16`, and `pady=(0, 10)` as its own gap to the content below it,
   where every sibling hero/toolbar card uses `(0, 12)`. Fixed both to
   match.

**Reviewed and confirmed NOT inconsistencies, so nothing was "fixed" by
accident:**
- Settings' 6 stacked cards (Campaign Safety, System Experience, License,
  SMTP, AI Cards, Danger Zone, Multi-Number) all consistently use
  `pady=(10, 0)` between each other — a different, but internally
  consistent, tighter gap specific to that screen's own denser two-column
  card grid, not drift from the `(0, 12)` convention used by single-column
  hero/toolbar layouts elsewhere.
- Subtitle/description text under card titles splits between
  `font=ctk.CTkFont(size=11)` (14 sites) and `size=12` (12 sites) app-wide —
  a mild, but plausibly intentional, distinction between compact field-level
  helper text and fuller card-level descriptions; not clearly broken the way
  the findings above were, so left alone rather than forcing an arbitrary
  unification.
- The 3-tier `corner_radius` system was already reviewed and confirmed
  intentional in the earlier Round 2 Item 7 polish audit.
"""

from __future__ import annotations

import customtkinter as ctk


def _find_label_by_text(widget, text):
    if isinstance(widget, ctk.CTkLabel):
        try:
            if widget.cget("text") == text:
                return widget
        except Exception:
            pass
    for child in widget.winfo_children():
        found = _find_label_by_text(child, text)
        if found is not None:
            return found
    return None


def test_compose_preview_style_cards_share_identical_title_font_size(app):
    """The real bug this item fixed: the Email panel's "SMTP connection" /
    "Recipients" / "Live preview" card titles used size=13 while the
    WhatsApp panel's structurally-identical "Preview" card (same row/column,
    same screen) used size=15."""
    compose = app.view_containers["Compose"]
    titles = ["Preview", "SMTP connection", "Recipients", "Live preview"]
    labels = {t: _find_label_by_text(compose, t) for t in titles}
    for t, lbl in labels.items():
        assert lbl is not None, f"expected to find a '{t}' card title label in Compose"
    sizes = {t: lbl.cget("font").cget("size") for t, lbl in labels.items()}
    reference = sizes["Preview"]
    for t, size in sizes.items():
        assert size == reference, (
            f"'{t}' card title font size is {size}, expected {reference} "
            f"(matching 'Preview') -- Compose's preview-style cards must "
            f"share one consistent title size, per Item 28")


def test_delivery_rate_card_title_matches_the_app_wide_major_card_size():
    """Delivery Rate's title used size=14, the sole size-14 outlier among
    every other major T.BG_SURFACE card's title (size=15) app-wide.

    Verified at the source level, not against a real running widget: this
    card lives inside `_build_reports_view`, already found in Item 26 to be
    unreachable dead code (never called from `_create_ui` or anywhere
    else), so no real MainWindow instance ever actually constructs it."""
    from pathlib import Path
    src = Path(__file__).resolve().parents[2] / "src" / "ui" / "main_window.py"
    text = src.read_text(encoding="utf-8")
    start = text.index("def _build_reports_view")
    end = text.index("def _build_campaign_history_view")
    body = text[start:end]
    assert 'text="Delivery Rate"' in body
    assert 'font=ctk.CTkFont(size=15, weight="bold")' in body.split('text="Delivery Rate"')[1][:120]


def test_history_hero_padding_matches_its_sibling_heroes(app):
    """History's hero card used padx=18 (title+subtitle) where every
    sibling hero (Campaigns home, Contacts, Reports & Analytics) uses
    padx=16, confirmed via each label's real grid info -- not just the
    source text. Compared against another live hero's own real grid_info()
    rather than a hardcoded literal: CTk applies its own DPI scaling to grid
    padding (confirmed directly -- padx=16 in source measured back as 20 via
    grid_info() on this machine's real 1.25x scaling), so any hardcoded
    expected pixel value would be scaling-factor-dependent and fragile."""
    settings = app.view_containers["Settings"]
    settings_hero_title = _find_label_by_text(settings, "Settings")
    assert settings_hero_title is not None, "expected to find the Settings hero title"
    reference_padx = settings_hero_title.grid_info()["padx"]

    history = app.view_containers["History"]
    title = _find_label_by_text(history, "Campaign history")
    subtitle = _find_label_by_text(
        history, "Full log of all email campaigns. Use Duplicate to re-use a campaign.")
    assert title is not None and subtitle is not None
    assert title.grid_info()["padx"] == reference_padx
    assert subtitle.grid_info()["padx"] == reference_padx
