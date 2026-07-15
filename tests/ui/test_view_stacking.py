"""Regression test for a real bug a user found by clicking through the app
themselves: navigating Cards -> Settings (and other view sequences) left the
Cards view's content visibly on screen underneath Settings' correct header/
breadcrumb/sidebar-highlight, because _animate_view_in's cleanup for the
*previous* animated-in container did `place_forget()` then `grid()` -- which
unmaps it, then immediately remaps/re-shows it in the same cell, instead of
actually hiding it. Once any view had been shown via the animated path, it
silently stayed visible forever afterward; since Tk's default sibling
stacking follows widget creation order and Cards is built last in
_create_ui(), Cards would silently show through on top of whatever view was
navigated to next.

The existing test_navigation_timing.py only ever asserted `_active_view` and
elapsed time -- never that the PREVIOUS view's content was actually hidden --
which is exactly why this shipped unnoticed. This file closes that gap by
asserting the real invariant: exactly one view container is ever mapped
(winfo_ismapped()) at a time, checked across every one of the 30 possible
ordered view-to-view transitions, not just the couple of sequences that
happened to surface the bug.
"""

from itertools import permutations

import pytest

MAIN_VIEWS = ["Campaigns", "Contacts", "Compose", "Settings", "History", "Cards"]

ALL_ORDERED_PAIRS = list(permutations(MAIN_VIEWS, 2))


def _mapped_views(app):
    return sorted(name for name, container in app.view_containers.items()
                   if container.winfo_ismapped())


@pytest.mark.parametrize("from_view,to_view", ALL_ORDERED_PAIRS)
def test_exactly_one_view_mapped_after_every_transition(app, from_view, to_view):
    app._show_view(from_view)
    app.update()
    app._show_view(to_view)
    app.update()

    mapped = _mapped_views(app)
    assert mapped == [to_view], (
        f"navigating {from_view} -> {to_view}: expected only {to_view!r} mapped, "
        f"got {mapped} -- a previous view's content is still visibly showing "
        f"through, not just an internal state mismatch"
    )


def test_cards_then_settings_exact_user_repro(app):
    """The literal sequence a real user hit: Cards, then Settings, showed
    Cards' "Card Identity"/"Live Card Preview" content under Settings' own
    correct header and active sidebar highlight."""
    app._show_view("Cards")
    app.update()
    app._show_view("Settings")
    app.update()

    assert _mapped_views(app) == ["Settings"]


def test_revisit_stress_no_stale_container_accumulates(app):
    """Repeatedly revisiting the same views in a long, mixed sequence must
    never leave more than one container mapped -- guards against the single-
    slot `_view_anim_container` tracking silently missing a container if the
    cleanup logic regresses again in a different way."""
    sequence = ["Settings", "Cards", "Contacts", "Cards", "History", "Settings",
                "Compose", "Campaigns", "Cards", "Settings", "Contacts"]
    for view in sequence:
        app._show_view(view)
        app.update()
        assert _mapped_views(app) == [view], f"broke at {view!r} mid-sequence"
