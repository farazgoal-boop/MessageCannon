"""Item 40: the user manual's content is real, structured data (not just
prose written once and never checked) -- these tests catch a malformed
block (a typo'd kind, an empty payload) or the deliverable regressing to
empty/missing sections, without needing a real Tk window."""

from __future__ import annotations

import importlib
from pathlib import Path

from docs.user_manual_content import CONTENT, MANUAL_SUPPORT_EMAIL, MANUAL_VERSION

DOCS_DIR = Path(__file__).resolve().parents[1] / "docs"

_VALID_KINDS = {"h1", "h2", "p", "ul", "ol", "table", "shot", "image", "note", "warn", "pagebreak"}


def test_every_block_has_a_known_kind_and_non_empty_payload():
    for kind, payload in CONTENT:
        assert kind in _VALID_KINDS, kind
        if kind == "pagebreak":
            assert payload is None
        elif kind in ("ul", "ol"):
            assert isinstance(payload, list) and len(payload) > 0
            assert all(isinstance(item, str) and item.strip() for item in payload)
        elif kind == "table":
            assert isinstance(payload, list) and len(payload) >= 2
            header = payload[0]
            for row in payload:
                assert len(row) == len(header)
        elif kind == "image":
            rel_path, caption = payload
            assert rel_path.strip() and caption.strip()
        else:
            assert isinstance(payload, str) and payload.strip()


def test_every_real_image_block_points_at_a_file_that_actually_exists():
    """A real embedded screenshot must actually be a real file on disk --
    not just a well-formed string that happens to look like a path."""
    images = [payload for kind, payload in CONTENT if kind == "image"]
    assert len(images) >= 1
    for rel_path, _caption in images:
        assert (DOCS_DIR / rel_path).is_file(), rel_path


def test_manual_covers_every_section_item_40_asked_for():
    """installation, setup wizard, importing contacts, composing (incl. AI),
    creating a card, sending safely, checking bounce results, the guided
    tour, and troubleshooting -- in that order."""
    headings = [text for kind, text in CONTENT if kind == "h1"]
    expected_fragments = [
        "Installing", "Setup Wizard", "Importing Your Contacts",
        "Composing Your First Message", "Creating a Marketing Card",
        "Sending a Campaign Safely", "Checking Delivery & Bounce Results",
        "Tour Mode", "Troubleshooting",
    ]
    joined = " | ".join(headings)
    positions = []
    for fragment in expected_fragments:
        assert any(fragment in h for h in headings) or fragment in joined, fragment
        idx = joined.find(fragment)
        positions.append(idx)
    # Sections appear in the requested order (each fragment found at a
    # strictly later position in the joined heading string than the last).
    assert positions == sorted(positions)


def test_screenshot_callouts_are_specific_not_generic():
    shots = [payload for kind, payload in CONTENT if kind == "shot"]
    assert len(shots) >= 5
    for shot in shots:
        assert len(shot) > 25  # a real, specific instruction, not a stub


def test_support_email_and_version_are_real_values():
    assert "@" in MANUAL_SUPPORT_EMAIL
    assert MANUAL_VERSION[0].isdigit()


def test_markdown_render_includes_every_screenshot_marker():
    build_module = importlib.import_module("scripts.build_user_manual")
    markdown = build_module.render_markdown()
    shot_count = sum(1 for kind, _ in CONTENT if kind == "shot")
    assert markdown.count("📸 **Screenshot needed:**") == shot_count
    assert MANUAL_SUPPORT_EMAIL in markdown
    for kind, text in CONTENT:
        if kind == "h1":
            assert f"## {text}" in markdown


def test_markdown_render_embeds_real_images_not_placeholder_callouts():
    build_module = importlib.import_module("scripts.build_user_manual")
    markdown = build_module.render_markdown()
    for kind, payload in CONTENT:
        if kind == "image":
            rel_path, caption = payload
            assert f"![{caption}]({rel_path})" in markdown
