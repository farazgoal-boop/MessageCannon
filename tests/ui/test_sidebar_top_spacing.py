"""Regression coverage for Item 6 of the Live Testing Findings pass: a large
empty vertical gap appeared below the sidebar header, before the nav items
(Campaigns, Contacts, ...) began.

Real root cause, found by direct widget-geometry measurement (not just code
reading) against a real running MainWindow: `_update_badge_slot` (the
always-packed wrapper around the sidebar's update-available pill, hidden
when no update exists) was constructed with only `width=1` -- no explicit
`height` -- so it silently took on CTkFrame's own ~200px default height
(measured 250px on this machine's 125% DPI scale) even while its one child
was unmapped. `width=1` had already been applied to fix a *different*,
previously-documented sidebar sizing bug (CLAUDE.md's "cold-start sidebar
position bug"), but `height` was missed there since that earlier bug was
about *width*, not vertical gaps.

Fix: `height=1` alongside the existing `width=1`.
"""

from __future__ import annotations


def test_update_badge_slot_collapses_to_near_zero_height_when_no_update(app):
    """The literal repro, measured directly: with no update available (the
    common case), the slot must not silently reserve ~200px of dead space
    between the brand block and the nav items."""
    app._update_info = None
    app._refresh_update_badge()
    app.update_idletasks()

    assert app._update_badge_slot.winfo_height() <= 5


def test_nav_frame_starts_close_to_the_brand_block_not_far_below_it(app):
    app._update_info = None
    app._refresh_update_badge()
    app.update_idletasks()

    brand_bottom = app._brand_title_label.winfo_y() + app._brand_title_label.winfo_height()
    nav_frame = None
    for child in app.sidebar.winfo_children():
        # nav_frame is the tall, expanding frame holding the nav buttons --
        # identify it structurally (packed with expand, sits after the
        # brand block) rather than by a private attribute name.
        if child.winfo_y() > brand_bottom and child.winfo_height() > 300:
            nav_frame = child
            break

    assert nav_frame is not None, "could not locate the nav frame to measure"
    gap = nav_frame.winfo_y() - brand_bottom
    # Legitimate spacing (padding, the collapse-toggle row, the divider
    # line) measures ~90px on this machine post-fix -- well under the
    # ~340px the pre-fix default-height bug produced. 150px leaves headroom
    # for other DPI scales while still catching a real regression of the
    # bug this test exists for.
    assert gap < 150, f"gap between brand block and nav items is {gap}px -- looks like a regression"
