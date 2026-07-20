"""Tests for HTML card generation."""

from __future__ import annotations

import base64
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.ui.card_creator_tab import (
    generate_html, CARD_STYLE_TEMPLATES, image_file_to_data_uri,
    ImageUploadError, MAX_UPLOAD_IMAGE_BYTES, _contrast_text_color,
)

# Smallest possible valid PNG (1x1 transparent pixel).
_TINY_PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk"
    "+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


class TestImageUpload(unittest.TestCase):
    """Round 2 item 4 (image upload): local files get embedded as base64
    data URIs so the exported card stays a self-contained standalone file."""

    def test_valid_image_becomes_data_uri(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(_TINY_PNG_BYTES)
            path = f.name
        try:
            uri = image_file_to_data_uri(path)
            self.assertTrue(uri.startswith("data:image/png;base64,"))
            decoded = base64.b64decode(uri.split(",", 1)[1])
            self.assertEqual(decoded, _TINY_PNG_BYTES)
        finally:
            Path(path).unlink()

    def test_oversized_image_rejected(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(b"0" * (MAX_UPLOAD_IMAGE_BYTES + 1))
            path = f.name
        try:
            with self.assertRaises(ImageUploadError):
                image_file_to_data_uri(path)
        finally:
            Path(path).unlink()

    def test_non_image_file_rejected(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(b"not an image")
            path = f.name
        try:
            with self.assertRaises(ImageUploadError):
                image_file_to_data_uri(path)
        finally:
            Path(path).unlink()

    def test_missing_file_rejected(self) -> None:
        with self.assertRaises(ImageUploadError):
            image_file_to_data_uri(str(Path(tempfile.gettempdir()) / "does_not_exist_12345.png"))

    def test_uploaded_image_renders_in_banner_section(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(_TINY_PNG_BYTES)
            path = f.name
        try:
            uri = image_file_to_data_uri(path)
            sections = [{"type": "banner", "data": {"url": uri}}]
            meta = {"app_name": "Test", "style": CARD_STYLE_TEMPLATES["Dark Premium"]}
            html = generate_html(sections, meta, for_preview=False)
            self.assertIn("data:image/png;base64,", html)
        finally:
            Path(path).unlink()


class TestCardGenerator(unittest.TestCase):
    """Card HTML generation tests."""

    def test_generate_basic_card(self) -> None:
        sections = [
            {"type": "text", "data": {"content": "Hello world", "size": "medium", "align": "left"}},
        ]
        meta = {
            "app_name": "Test App",
            "icon": "⭐",
            "tagline": "Testing",
            "accent": "#6c63ff",
            "org": "Faraz Automation",
            "style": CARD_STYLE_TEMPLATES["Dark Premium"],
        }
        html = generate_html(sections, meta)
        self.assertIn("Test App", html)
        self.assertIn("Hello world", html)
        self.assertIn("<!DOCTYPE html>", html)

    def test_buy_now_link(self) -> None:
        sections = [{"type": "price", "data": {"price": "$89", "old_price": "", "note": ""}}]
        meta = {
            "app_name": "Test",
            "accent": "#6c63ff",
            "buy_link": "https://gumroad.com/l/test-product",
            "style": CARD_STYLE_TEMPLATES["Dark Premium"],
        }
        html = generate_html(sections, meta, for_preview=False)
        self.assertIn('href="https://gumroad.com/l/test-product"', html)
        self.assertIn("BUY NOW →", html)

    def test_youtube_preview_uses_thumbnail(self) -> None:
        sections = [{"type": "youtube", "data": {"url": "https://youtube.com/watch?v=dQw4w9WgXcQ"}}]
        meta = {"app_name": "Test", "style": CARD_STYLE_TEMPLATES["Dark Premium"]}
        preview = generate_html(sections, meta, for_preview=True)
        export = generate_html(sections, meta, for_preview=False)
        self.assertIn("img.youtube.com/vi/dQw4w9WgXcQ", preview)
        self.assertNotIn("<iframe", preview)
        self.assertIn("<iframe", export)

    def test_links_section_no_raw_html_leak(self) -> None:
        """Ensure link URLs/labels are escaped and never leak raw HTML as visible text."""
        sections = [{
            "type": "links",
            "data": {"links": [{"kind": "youtube", "label": "YouTube",
                                "url": "https://youtube.com/@faraz"}]},
        }]
        meta = {
            "app_name": "Test",
            "icon": "📨",
            "tagline": "Test",
            "accent": "#6c63ff",
            "org": "Faraz Automation",
            "wa": "+92",
            "email": "a@b.com",
            "addr": "Karachi",
            "style": CARD_STYLE_TEMPLATES["Dark Premium"],
        }
        result = generate_html(sections, meta, for_preview=False)
        self.assertIn('target="_blank"', result)
        self.assertEqual(result.count("<a href="), result.count("</a>"))
        self.assertIn('href="https://youtube.com/@faraz"', result)
        import re
        anchors = re.findall(
            r'<a href="([^"]*)" target="_blank" style="display:flex[^"]*">',
            result,
        )
        self.assertEqual(anchors, ["https://youtube.com/@faraz"])

    def test_links_section_escapes_quotes_in_url(self) -> None:
        """Quoted pasted URLs must not break the href attribute."""
        sections = [{
            "type": "links",
            "data": {"links": [{"kind": "youtube", "label": "YouTube",
                                "url": '"https://youtube.com/@faraz"'}]},
        }]
        meta = {"app_name": "Test", "style": CARD_STYLE_TEMPLATES["Dark Premium"]}
        result = generate_html(sections, meta, for_preview=False)
        self.assertIn('href="https://youtube.com/@faraz"', result)
        self.assertNotRegex(result, r'href=""\s*target=')
        self.assertNotRegex(result, r'href="https://[^"]*""\s*target=')

    def test_no_org_defaults_to_generic_not_developer_contact_info(self) -> None:
        """Round 2 item 4: org/wa/email/addr previously fell back to the
        developer's own real contact info (Faraz Automation, a real phone
        number, a real email) whenever a caller omitted them -- meaning
        every MessageCannon user's card silently advertised the developer's
        details instead of their own. Confirms the fallback is now empty,
        not personal data, and that an empty Contact Footer section renders
        no stray empty lines."""
        sections = [{"type": "contact", "data": {}}]
        meta = {"app_name": "Test", "style": CARD_STYLE_TEMPLATES["Dark Premium"]}
        html = generate_html(sections, meta, for_preview=False)
        self.assertNotIn("Faraz Automation", html)
        self.assertNotIn("2400657", html)
        self.assertNotIn("farazgoal", html)
        self.assertNotIn("Karachi", html)
        # No empty "Created with MessageCannon Pro · " (trailing separator
        # with nothing after it) when org is blank.
        self.assertIn("Created with MessageCannon Pro<", html)

    def test_contact_section_omits_blank_fields(self) -> None:
        """Only fields the user actually filled in should render -- no bare
        '📱 ' with nothing after it for a blank phone/email/address."""
        sections = [{"type": "contact", "data": {}}]
        meta = {
            "app_name": "Test", "org": "Acme Inc",
            "style": CARD_STYLE_TEMPLATES["Dark Premium"],
        }
        html = generate_html(sections, meta, for_preview=False)
        self.assertIn("Acme Inc", html)
        self.assertNotIn("📱 <", html)
        self.assertNotIn("✉️ <", html)
        self.assertNotIn("📍<", html)

    def test_all_templates_produce_html(self) -> None:
        for name, style in CARD_STYLE_TEMPLATES.items():
            meta = {"app_name": name, "style": style, "accent": style["accent"]}
            html = generate_html([], meta)
            self.assertIn(name, html, msg=f"Template {name} failed")


class TestHeaderSection(unittest.TestCase):
    """Round 2 item 4: the branded header used to always render first
    regardless of `sections`, unlike every other section (banner, text,
    price, ...) which are addable/removable/reorderable. Now it's a real
    "header" section type like the rest."""

    def test_no_header_section_means_no_header_renders(self) -> None:
        sections = [{"type": "text", "data": {"content": "Hi", "size": "medium", "align": "left"}}]
        meta = {"app_name": "Test App", "icon": "🚀", "tagline": "Tag",
                "style": CARD_STYLE_TEMPLATES["Dark Premium"]}
        html = generate_html(sections, meta)
        # Title tag still carries the app name even with no header section.
        self.assertIn("Test App", html)
        # But the header's distinctive icon-badge markup must be absent.
        self.assertNotIn("🚀", html)

    def test_header_section_renders_identity_fields(self) -> None:
        sections = [{"type": "header", "data": {}}]
        meta = {"app_name": "Test App", "icon": "🚀", "tagline": "My Tagline",
                "org": "Acme Inc", "style": CARD_STYLE_TEMPLATES["Dark Premium"]}
        html = generate_html(sections, meta)
        self.assertIn("Test App", html)
        self.assertIn("🚀", html)
        self.assertIn("My Tagline", html)
        self.assertIn("Acme Inc", html)

    def test_header_can_be_reordered_after_banner(self) -> None:
        sections = [
            {"type": "banner", "data": {"url": "https://example.com/b.jpg"}},
            {"type": "header", "data": {}},
        ]
        meta = {"app_name": "Test App", "icon": "🚀",
                "style": CARD_STYLE_TEMPLATES["Dark Premium"]}
        html = generate_html(sections, meta)
        self.assertLess(html.index("example.com/b.jpg"), html.index("🚀"))


class TestCustomBackground(unittest.TestCase):
    """Round 2 item 4 (custom background): a separate style dict from the
    hand-picked CARD_STYLE_TEMPLATES, built from a user's own color/image
    choice via CardCreatorV2._custom_style -- generate_html itself doesn't
    know or care whether a style dict came from a template or is custom,
    so these test the dict shape directly."""

    def test_contrast_text_color_picks_readable_color(self) -> None:
        self.assertEqual(_contrast_text_color("#ffffff"), "rgba(20,20,20,0.85)")
        self.assertEqual(_contrast_text_color("#000000"), "rgba(255,255,255,0.85)")
        # Malformed input must never raise -- falls back to a safe default.
        self.assertEqual(_contrast_text_color("not-a-color"), "rgba(255,255,255,0.85)")

    def test_custom_solid_color_renders_in_card(self) -> None:
        style = {"bg": "#e8f0ff", "body_bg": "#e8f0ff",
                 "text": "rgba(20,20,20,0.85)", "header_bg": "#e8f0ff", "accent": "#4f46e5"}
        sections = [{"type": "text", "data": {"content": "Hello", "size": "medium", "align": "left"}}]
        meta = {"app_name": "Test", "style": style}
        html = generate_html(sections, meta)
        self.assertIn("#e8f0ff", html)
        self.assertIn("rgba(20,20,20,0.85)", html)

    def test_custom_image_background_renders_as_css_url(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(_TINY_PNG_BYTES)
            path = f.name
        try:
            uri = image_file_to_data_uri(path)
            bg_value = f"url({uri}) center center / cover no-repeat"
            style = {"bg": bg_value, "body_bg": bg_value,
                     "text": "rgba(255,255,255,0.85)", "header_bg": bg_value}
            meta = {"app_name": "Test", "style": style}
            html = generate_html([], meta)
            self.assertIn(f"background:{bg_value}", html)
        finally:
            Path(path).unlink()


if __name__ == "__main__":
    unittest.main()
