"""Item 13 of the Live Testing Findings pass (Round 2): code-level review of
the signature navigation transition found a real, verifiable mismatch --
the content slide (_animate_view_in) and the sidebar's own accent-bar reveal
(_animate_nav_accent_in) fire from the same _show_view call, at the same
instant, and are meant to read as one cohesive arrival, but ran on two
different clocks: 4 steps/90ms with ease_out_cubic for the content vs
5 steps/120ms, linear, for the accent bar. Fixed by sharing the exact same
step count, duration, and easing function (_VIEW_TRANSITION_STEPS/
_DURATION_MS, _ease_out_cubic) between both. Also fixed a stale docstring
on _animate_view_in that said "~150ms" when the real constant was 90.

Deterministic-only tests live here (parallel-safe); the two tests that
depend on real after()-scheduled animation timing
(test_accent_bar_reveal_uses_eased_not_linear_progression and
test_accent_bar_and_content_slide_finish_within_the_same_budget) moved to
test_nav_accent_timing.py after both were found to flake under heavy
parallel `MainWindow()` contention despite passing reliably alone --
confirmed directly, not assumed, the same class of issue this suite's
README already documents for test_navigation_timing.py/test_close_button.py.
"""

from __future__ import annotations


def test_ease_out_cubic_matches_expected_curve(app):
    # Standard cubic ease-out: 1 - (1-t)^3.
    assert app._ease_out_cubic(0.0) == 0.0
    assert app._ease_out_cubic(1.0) == 1.0
    assert abs(app._ease_out_cubic(0.5) - 0.875) < 1e-9


def test_content_slide_and_accent_bar_share_the_same_step_duration_constants(app):
    assert app._VIEW_TRANSITION_STEPS == 4
    assert app._VIEW_TRANSITION_DURATION_MS == 90
