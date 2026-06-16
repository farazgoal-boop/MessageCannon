"""Tests for HTML card generation."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.ui.card_creator_tab import generate_html, CARD_STYLE_TEMPLATES


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

    def test_all_templates_produce_html(self) -> None:
        for name, style in CARD_STYLE_TEMPLATES.items():
            meta = {"app_name": name, "style": style, "accent": style["accent"]}
            html = generate_html([], meta)
            self.assertIn(name, html, msg=f"Template {name} failed")


if __name__ == "__main__":
    unittest.main()
