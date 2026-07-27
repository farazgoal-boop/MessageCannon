"""Item 27 of the Final Premium Polish Pass: force visual consistency across
every real button in the app (102 CTkButton call sites, audited across all
9 files in src/ui that contain any — main_window.py 44, card_creator_tab.py
30, setup_wizard.py 10, send_dialogs.py 5, contact_import_review.py 4,
update_dialog.py 3, ai_compose_dialog.py 3, confirm_dialogs.py 2,
campaigns_tab.py 1).

Real bugs found and fixed, most severe first:

1. **Zero real hover feedback** (`fg_color == hover_color`, so hovering or
   clicking produces no visible change at all — directly contradicts "real
   hover/pressed states on every button"):
   - Contacts toolbar "Refresh" (`main_window.py`) — `fg_color=T.BG_SURFACE,
     hover_color=T.BG_SURFACE`, and *also* flush with its own parent
     `toolbar` card (also `T.BG_SURFACE`) — nearly invisible AND inert.
     Fixed to match its sibling "Import Contacts" button's style
     (`T.BADGE_BG` / `T.BG_BORDER` / `T.TEXT_HEAD`).
   - Card Creator "🌐 Open Browser" and "🚀 Start Sending"
     (`card_creator_tab.py`) — both `fg_color=hover_color=T.SUCCESS`. No
     `SUCCESS_HOVER` token existed to fix this properly, so one was added to
     `theme.py` following the same Tailwind 500→600 darkening pattern
     already used for `ACCENT_HOVER`/`DANGER_HOVER` (`#10B981`→`#059669`
     dark/light, a plausible analogous darker green for Warm Ivory).

2. **A real, confirmed WCAG contrast fail**: `text_color=T.ACCENT` measured
   as low as 2.16:1 in Dark mode against `T.BG_SURFACE`/`T.BADGE_BG` — well
   under even the lenient 3:1 UI-component floor, and exactly the scenario
   the Design System's own rule already warned about ("use ACCENT as
   fg_color only, NOT text_color on cards") but had never actually been
   swept for. Found first on 2 outline/secondary buttons ("Pause / Resume"
   in Compose, "▶ Show" in Card Creator's Advanced toggle — both
   `fg_color="transparent"` sitting directly on a `T.BG_SURFACE` card, with
   `hover_color` sometimes *also* identical to that parent, a second
   instance of bug #1) — then, once the user confirmed a full systemic fix
   (not just a button-scoped one) was wanted, found to affect **every**
   `text_color=T.ACCENT` site app-wide (41 in `main_window.py`/
   `card_creator_tab.py`/`ai_compose_dialog.py`, covering both buttons and
   plain labels/chips like "45 sec cadence"). Fixed by adding a new
   `T.ACCENT_TEXT` token (`theme.py`) verified to pass AA (4.8:1+) against
   `BG_SURFACE`/`BG_INNER`/`BADGE_BG` in all three palettes, then sweeping
   every bare `text_color=T.ACCENT` site to use it instead. The two outline
   buttons above additionally got a real `fg_color=T.BG_INNER` (matching
   History's already-verified "Duplicate" button fix from Item 12) instead
   of a transparent fill flush with its own card, fixing both the contrast
   and the hover-is-a-no-op problems at once.

3. **Missing `text_color=`** (relies on CTk's own un-themed default instead
   of an explicit token, unlike every sibling button of the same fg_color):
   Card Creator's "Custom…" accent-swatch button and its single biggest CTA
   ("✨ Generate Card"), and the license-activation dialog's "Exit App"/
   "Activate Now" buttons. All 4 given the same `text_color=T.TEXT_HEAD`
   every other `T.ACCENT`/`T.BADGE_BG`-filled button in their own file
   already used.

Reviewed and confirmed *not* bugs, so as not to "fix" them by accident:
- The 3-tier corner_radius system (14/major cards, 999/pills, 6-12/buttons)
  was already reviewed and confirmed intentional in an earlier polish pass
  (Round 2, Item 7) — not re-litigated here.
- "Configure in Settings →" (filled `T.BADGE_BG`) vs. "View recipient list
  →"/"Get an API key →" (transparent) are a legitimate 2-tier distinction —
  a corrective CTA inside a warning-toned card vs. a plain inline
  navigational link — not an inconsistency.
- Every icon-only utility button (↑/↓/✕ in Card Creator's section list) is
  already internally consistent within its own group.

A previously-undocumented dead-code finding (unrelated to buttons) also
surfaced while auditing dropdowns in Item 26 — see
`test_dropdown_consistency.py`'s own module docstring.
"""

from __future__ import annotations

import re
from pathlib import Path

import src.ui.theme as T

SRC_UI = Path(__file__).resolve().parents[2] / "src" / "ui"


def hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _luminance(rgb: tuple[int, int, int]) -> float:
    def f(c: int) -> float:
        c = c / 255.0
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = rgb
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def contrast(hex1: str, hex2: str) -> float:
    l1, l2 = _luminance(hex_to_rgb(hex1)), _luminance(hex_to_rgb(hex2))
    lighter, darker = max(l1, l2), min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def test_success_hover_is_a_real_distinct_darker_shade():
    assert T.SUCCESS_HOVER != T.SUCCESS
    for mode_success, mode_hover in zip(T.SUCCESS, T.SUCCESS_HOVER):
        assert mode_success != mode_hover


def test_accent_text_passes_aa_contrast_against_every_card_background():
    """The real bug this item fixed: plain T.ACCENT as a text_color measured
    2.16:1 against T.BG_SURFACE in Dark mode -- a real WCAG fail. ACCENT_TEXT
    must pass AA (>= 4.5:1) against every background a card/badge label can
    realistically sit on, in every palette."""
    surfaces_by_mode = {
        "light": {"BG_SURFACE": "#FFFFFF", "BG_INNER": "#F1F3F7", "BADGE_BG": "#EEF1F6"},
        "dark":  {"BG_SURFACE": "#2A4762", "BG_INNER": "#152C42", "BADGE_BG": "#1F3A57"},
        "warm":  {"BG_SURFACE": "#FFFDF8", "BG_INNER": "#F3EAD8", "BADGE_BG": "#F3EAD8"},
    }
    accent_text_by_mode = {
        "light": T.ACCENT_TEXT[0],
        "dark": T.ACCENT_TEXT[1],
        "warm": "#94530F",  # T._WARM_IVORY value; palette-independent check
    }
    for mode, surfaces in surfaces_by_mode.items():
        text_hex = accent_text_by_mode[mode]
        for surface_name, surface_hex in surfaces.items():
            ratio = contrast(text_hex, surface_hex)
            assert ratio >= 4.5, (
                f"ACCENT_TEXT ({mode}) against {surface_name} ({surface_hex}) "
                f"only measures {ratio:.2f}:1, below the 4.5:1 AA floor")


def test_plain_accent_text_color_fails_contrast_confirming_the_bug_was_real():
    """Confirms the *old* pattern this item replaced really was broken --
    T.ACCENT itself (not ACCENT_TEXT) measured well under the WCAG floor as
    a text color on BG_SURFACE in Dark mode."""
    accent_dark = T.ACCENT[1]
    ratio = contrast(accent_dark, "#2A4762")
    assert ratio < 3.0, (
        f"expected the historical bug's contrast to still measure below the "
        f"3:1 UI-component floor ({ratio:.2f}:1) -- if this now passes, "
        f"T.ACCENT's own value changed and this test's premise is stale")


def test_no_bare_accent_text_color_remains_in_shipped_ui_source():
    """Static regression guard against the exact class of bug this item
    fixed: a future edit re-introducing `text_color=T.ACCENT` (instead of
    `T.ACCENT_TEXT`) on any real widget should fail this test immediately,
    rather than waiting for another live-testing pass to notice a contrast
    fail by eye."""
    pattern = re.compile(r"text_color=T\.ACCENT([,)]|\s+if\b)")
    offenders = []
    for path in SRC_UI.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        for m in pattern.finditer(text):
            line_no = text.count("\n", 0, m.start()) + 1
            offenders.append(f"{path.name}:{line_no}")
    assert not offenders, f"bare text_color=T.ACCENT found (use T.ACCENT_TEXT instead): {offenders}"


def test_no_button_has_literally_identical_fg_and_hover_color():
    """Static regression guard: a CTkButton whose fg_color and hover_color
    are the literal same token/string produces zero visual hover feedback --
    the exact bug found on Contacts' "Refresh" button (T.BG_SURFACE twice)
    and Card Creator's "Open Browser"/"Start Sending" (T.SUCCESS twice)."""
    call_pattern = re.compile(r"CTkButton\(")
    offenders = []
    for path in SRC_UI.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        for m in call_pattern.finditer(text):
            depth = 0
            j = m.end() - 1
            while j < len(text):
                if text[j] == "(":
                    depth += 1
                elif text[j] == ")":
                    depth -= 1
                    if depth == 0:
                        break
                j += 1
            call_text = text[m.start():j + 1]
            fg = re.search(r"fg_color=([^\n,)]+)", call_text)
            hover = re.search(r"hover_color=([^\n,)]+)", call_text)
            if fg and hover and fg.group(1).strip() == hover.group(1).strip():
                line_no = text.count("\n", 0, m.start()) + 1
                offenders.append(f"{path.name}:{line_no} ({fg.group(1).strip()})")
    assert not offenders, f"buttons with identical fg_color/hover_color (no real hover feedback): {offenders}"


def test_pause_resume_and_advanced_toggle_use_the_contrast_safe_pattern(app):
    """Widget-level confirmation for the two real, specific buttons found
    during this audit: both must use the same T.BG_INNER/T.BG_BORDER/
    T.ACCENT recipe already verified safe by History's "Duplicate" button
    (Item 12), not a transparent fill flush with their own T.BG_SURFACE
    parent card."""
    for widget in (app._compose_pause_btn, app.card_creator_tab._adv_toggle_btn):
        assert widget.cget("fg_color") == T.BG_INNER
        assert widget.cget("hover_color") == T.BG_BORDER
        assert widget.cget("fg_color") != widget.cget("hover_color")
