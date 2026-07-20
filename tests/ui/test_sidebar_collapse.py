"""Regression/coverage test for the collapsible sidebar feature
(_toggle_sidebar_collapsed / _apply_sidebar_collapsed_visuals in
main_window.py). CLAUDE.md's "Sidebar redesign" section flags this feature
as shipped with no checkpoint entry, no test coverage, and no post-hoc
screenshot verification -- this file closes the test-coverage half of that
gap. Persistence-across-restart coverage lives in the sibling
test_sidebar_collapse_persist.py, split out because it needs two sequential
MainWindow() root creations and the rest of this file's tests share one.

Uses a dedicated, module-scoped, fresh-DB MainWindow rather than the shared
`app` fixture from conftest.py, for the same reason test_light_theme_default.py
and test_close_button.py do: _toggle_sidebar_collapsed() calls
_save_settings(), which would otherwise write real changes into the live
production settings blob shared with theme/SMTP/etc. Module-scoped (not
function-scoped) because more than ~2-3 sequential tkinter root-window
creations in one process is unreliable here (see tests/ui/README.md) --
confirmed directly: an earlier function-scoped version of this fixture threw
"main thread is not in main loop" partway through this file's test list.
"""

import tkinter as tk

import pytest


def _close_any_toplevel(window) -> None:
    def walk(widget):
        for child in widget.children.values():
            if isinstance(child, tk.Toplevel):
                return child
            found = walk(child)
            if found:
                return found
        return None
    top = walk(window)
    if top is not None:
        top.destroy()


def _ensure_expanded(window) -> None:
    """Force a known starting state regardless of prior test order, since
    the window is shared (module-scoped) across every test in this file."""
    if window._sidebar_collapsed:
        window._toggle_sidebar_collapsed()
        window.update()


@pytest.fixture(scope="module")
def window(tmp_path_factory):
    from src.database import db_manager as db_manager_module

    mp = pytest.MonkeyPatch()
    fresh_db_path = str(tmp_path_factory.mktemp("sidebar_collapse") / "test.db")
    mp.setattr(db_manager_module, "get_database_path", lambda: fresh_db_path)
    db_manager_module.DatabaseManager._instance = None

    from src.ui.main_window import MainWindow

    win = MainWindow()
    _close_any_toplevel(win)
    win.update()
    try:
        yield win
    finally:
        try:
            if win.winfo_exists():
                win.destroy()
        except Exception:
            pass
        db_manager_module.DatabaseManager._instance = None
        mp.undo()


def test_starts_expanded_by_default(window):
    _ensure_expanded(window)
    assert window._sidebar_collapsed is False
    assert window.sidebar_collapse_btn.cget("text") == "«"


def test_toggle_flips_state_and_button_glyph(window):
    _ensure_expanded(window)

    window._toggle_sidebar_collapsed()
    window.update()
    assert window._sidebar_collapsed is True
    assert window.sidebar_collapse_btn.cget("text") == "»"

    window._toggle_sidebar_collapsed()
    window.update()
    assert window._sidebar_collapsed is False
    assert window.sidebar_collapse_btn.cget("text") == "«"


def test_collapse_shrinks_sidebar_column_width(window):
    _ensure_expanded(window)
    expanded_minsize = window.grid_columnconfigure(0)["minsize"]
    assert int(expanded_minsize) == window.SIDEBAR_WIDTH_EXPANDED

    window._toggle_sidebar_collapsed()
    window.update()
    collapsed_minsize = window.grid_columnconfigure(0)["minsize"]
    assert int(collapsed_minsize) == window.SIDEBAR_WIDTH_COLLAPSED
    assert window.SIDEBAR_WIDTH_COLLAPSED < window.SIDEBAR_WIDTH_EXPANDED

    _ensure_expanded(window)


def test_collapse_actually_shrinks_rendered_sidebar_width(window):
    """The test above only checked the *configured* grid_columnconfigure
    minsize -- a floor, not the real on-screen width -- which let a real bug
    ship silently: the collapsed sidebar rendered at ~158px, not ~72px,
    because the 58x58 brand logo image (and, before an earlier fix in this
    same session, the nav buttons' own unconstrained default width) kept
    requesting more space than the column's minsize regardless of the
    collapsed flag. Asserts the real winfo_width() actually shrinks close to
    SIDEBAR_WIDTH_COLLAPSED, not just that the config value changed."""
    _ensure_expanded(window)
    window.update()
    expanded_width = window.sidebar.winfo_width()
    assert expanded_width >= window.SIDEBAR_WIDTH_EXPANDED

    window._toggle_sidebar_collapsed()
    window.update()
    collapsed_width = window.sidebar.winfo_width()
    assert collapsed_width <= window.SIDEBAR_WIDTH_COLLAPSED + 20, (
        f"collapsed sidebar rendered at {collapsed_width}px, expected close "
        f"to {window.SIDEBAR_WIDTH_COLLAPSED}px")
    assert collapsed_width < expanded_width - 100

    _ensure_expanded(window)


def test_collapse_hides_informational_widgets(window):
    _ensure_expanded(window)
    informational = [
        window._brand_title_label,
        window._brand_subtitle_label,
        window.sidebar_premium_panel,
        window.sidebar_session_status_label,
        window.sidebar_license_badge,
    ]
    for widget in informational:
        assert widget.winfo_ismapped(), f"{widget} should be visible while expanded"

    window._toggle_sidebar_collapsed()
    window.update()
    for widget in informational:
        assert not widget.winfo_ismapped(), (
            f"{widget} should be hidden while collapsed -- none of this "
            f"informational content fits meaningfully at "
            f"{window.SIDEBAR_WIDTH_COLLAPSED}px")

    window._toggle_sidebar_collapsed()
    window.update()
    for widget in informational:
        assert widget.winfo_ismapped(), f"{widget} should reappear after re-expanding"


def test_reexpand_preserves_bottom_widget_stacking_order(window):
    """Real bug found via before/after screenshot comparison while verifying
    this feature: _apply_sidebar_collapsed_visuals() re-packed the bottom
    sidebar widgets (Premium Access panel, session status, license badge)
    in the REVERSE of the order _create_ui() originally packed them in.
    Since all three use side="bottom" packing, each newly-packed widget
    stacks ABOVE the previous ones -- so replaying them in reverse order
    silently flipped their on-screen order after every collapse -> expand
    round trip. Guards against that regressing again."""
    _ensure_expanded(window)
    expected_top_to_bottom = [
        window.sidebar_premium_panel,
        window.sidebar_session_status_label,
        window.sidebar_license_badge,
    ]
    baseline_order = sorted(expected_top_to_bottom, key=lambda w: w.winfo_y())
    assert baseline_order == expected_top_to_bottom, (
        "sanity check on the initial, never-toggled layout failed -- test "
        "assumptions about pack order are wrong")

    window._toggle_sidebar_collapsed()
    window.update()
    window._toggle_sidebar_collapsed()
    window.update()

    after_round_trip = sorted(expected_top_to_bottom, key=lambda w: w.winfo_y())
    assert after_round_trip == expected_top_to_bottom, (
        "collapse -> re-expand round trip reversed the bottom sidebar "
        "widgets' visual stacking order")


def test_collapse_switches_nav_buttons_to_icon_only(window):
    _ensure_expanded(window)
    view_name, (icon, label) = next(iter(window.sidebar_nav_meta.items()))
    button = window.sidebar_buttons[view_name]

    assert button.cget("text") == f"{icon}  {label}"
    assert button.cget("anchor") == "w"

    window._toggle_sidebar_collapsed()
    window.update()
    assert button.cget("text") == icon
    assert button.cget("anchor") == "center"

    window._toggle_sidebar_collapsed()
    window.update()
    assert button.cget("text") == f"{icon}  {label}"
    assert button.cget("anchor") == "w"


def test_nav_still_switches_views_while_collapsed(window):
    """The collapse toggle only changes chrome -- navigation itself must
    keep working normally with icon-only buttons."""
    _ensure_expanded(window)
    window._toggle_sidebar_collapsed()
    window.update()

    window._show_view("Settings")
    window.update()
    assert window._active_view == "Settings"
    assert window.view_containers["Settings"].winfo_ismapped()

    _ensure_expanded(window)


def test_collapse_toggle_tooltip_text_matches_state(window):
    """Item 1 (Round 2): mirrors JobMind Match's real
    `toggle.title = collapsed ? "Expand..." : "Collapse..."` -- the reference
    this project actually has a real collapse toggle (unlike Career Copilot,
    which has none), just not this specific dynamic-tooltip detail before
    now."""
    _ensure_expanded(window)
    assert window._collapse_btn_tooltip.text == "Collapse sidebar"

    window._toggle_sidebar_collapsed()
    window.update()
    assert window._collapse_btn_tooltip.text == "Expand sidebar"

    window._toggle_sidebar_collapsed()
    window.update()
    assert window._collapse_btn_tooltip.text == "Collapse sidebar"


def test_collapse_toggle_pulses_then_restores(window):
    """A real smooth width transition (matching JobMind's CSS
    `transition: width`) was measured and found to cost ~40-210ms PER STEP
    on this app's real views -- infeasible for a smooth animation. This
    single-widget color pulse is the feasible substitute: verifies the
    button's fg_color actually changes to accent immediately (synchronous,
    no relayout) and is scheduled to restore afterward, without asserting a
    specific wall-clock delay (that part is inherently timing-sensitive --
    see the call site's own note about _save_settings() I/O being able to
    outlast the pulse window)."""
    _ensure_expanded(window)
    from src.ui import theme as T
    btn = window.sidebar_collapse_btn
    resting_color = btn.cget("fg_color")

    window._pulse_collapse_toggle()
    assert btn.cget("fg_color") == T.ACCENT
    assert window._collapse_pulse_after_id is not None

    window.after_cancel(window._collapse_pulse_after_id)
    btn.configure(fg_color=resting_color)
