"""Regression tests for the Setup Wizard sizing/scrolling bug found via real
live testing: on a real user's screen/DPI scaling, the wizard's fixed
620x660, non-resizable, non-scrolling window let the email_creds step's ~30
stacked widgets exceed the pack cavity, squeezing the footer (Continue/Test
buttons) out entirely -- unmapped, unreachable by mouse or Tab.

Fix: scrollable step content (`wizard.content`, a real CTkScrollableFrame)
separated from a pinned footer (`wizard.footer`) that lives outside the
scroll region, plus a resizable window sized/centered to the real screen.
These tests simulate the constrained-window scenario directly (no way to
fake a different real screen resolution in this environment) by shrinking
the wizard to a deliberately tiny geometry after rendering the heaviest
step and confirming the footer buttons stay mapped and reachable.
"""

from __future__ import annotations

import customtkinter as ctk
import pytest

from src.ui.setup_wizard import SetupWizard


@pytest.fixture()
def wizard(app):
    w = SetupWizard(app, force_restart=True)
    app.update()
    yield w
    try:
        if w.winfo_exists():
            w.destroy()
    except Exception:
        pass
    app.update()


def test_content_is_scrollable(wizard):
    assert isinstance(wizard.content, ctk.CTkScrollableFrame)


def test_footer_is_separate_from_scrollable_content(wizard):
    assert wizard.footer is not wizard.content
    assert wizard.footer.master is wizard
    # CTkScrollableFrame wraps itself in an internal canvas -- check it's
    # gridded directly under the wizard (row 0) rather than nested inside
    # the footer, and that footer occupies the row below it.
    assert wizard.content.grid_info().get("row") == 0
    assert wizard.footer.grid_info().get("row") == 1


def test_window_is_resizable(wizard):
    assert wizard.resizable()[0] == 1
    assert wizard.resizable()[1] == 1


def test_footer_buttons_stay_mapped_on_heaviest_step_even_when_shrunk(wizard):
    """email_creds is the tallest step (provider dropdown + 6 fields, each
    with a label/entry/help line -- confirmed the original crash repro)."""
    wizard.channels = ["email"]
    wizard.channel_index = 0
    wizard._goto("email_creds")
    wizard.update_idletasks()

    # Simulate a real constrained screen: shrink far below the content's
    # natural height, well past where the old single-frame layout would
    # have squeezed the footer out of the pack cavity entirely.
    wizard.geometry("500x260")
    wizard.update_idletasks()
    wizard.update()

    assert wizard.footer.winfo_ismapped()
    buttons = [c for c in wizard.footer.winfo_children() if isinstance(c, ctk.CTkButton)]
    assert any(b.cget("text") == "Continue" for b in buttons)
    for b in buttons:
        assert b.winfo_ismapped()
        assert b.winfo_width() > 0
        assert b.winfo_height() > 0


def test_scrollable_content_holds_all_email_fields_even_when_shrunk(wizard):
    """The fields themselves aren't lost -- they're still real children of
    the scrollable area, just scrollable instead of squeezed/clipped."""
    wizard.channels = ["email"]
    wizard.channel_index = 0
    wizard._goto("email_creds")
    wizard.geometry("500x260")
    wizard.update_idletasks()

    entries = [w for w in wizard.content.winfo_children() if isinstance(w, ctk.CTkEntry)]
    # Host, Port, Username, Password, Sender name, Sender email
    assert len(entries) == 6


def test_wizard_opens_within_screen_bounds(wizard):
    """_size_and_center must never request a size larger than the real
    screen (would itself reproduce an unreachable-footer scenario on a
    small/constrained display), and must be centered (non-negative,
    symmetric-ish offsets)."""
    wizard.update_idletasks()
    screen_w = wizard.winfo_screenwidth()
    screen_h = wizard.winfo_screenheight()
    assert wizard.winfo_width() <= screen_w
    assert wizard.winfo_height() <= screen_h
    assert wizard.winfo_x() >= 0
    assert wizard.winfo_y() >= 0
