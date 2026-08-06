"""Item 33 of the multi-product generalization pass: real "Import HTML
Card/Page" feature. Pure-logic tests for src/core/html_import.py -- no Tk
widgets involved, so these run in the fast plain `tests/` suite rather than
the slow `tests/ui/` one.
"""

from __future__ import annotations

import base64

import pytest

from src.core.html_import import (
    HtmlImportError,
    extract_suggested_subject,
    import_html_file,
    inline_relative_images,
    read_html_file,
)


def test_read_html_file_rejects_missing_file(tmp_path):
    with pytest.raises(HtmlImportError, match="not found"):
        read_html_file(tmp_path / "does_not_exist.html")


def test_read_html_file_rejects_wrong_extension(tmp_path):
    path = tmp_path / "notes.txt"
    path.write_text("<html></html>")
    with pytest.raises(HtmlImportError, match="doesn't look like"):
        read_html_file(path)


def test_read_html_file_rejects_empty_file(tmp_path):
    path = tmp_path / "empty.html"
    path.write_text("")
    with pytest.raises(HtmlImportError, match="empty"):
        read_html_file(path)


def test_read_html_file_rejects_oversized_file(tmp_path, monkeypatch):
    import src.core.html_import as html_import_module

    monkeypatch.setattr(html_import_module, "MAX_IMPORT_HTML_BYTES", 10)
    path = tmp_path / "big.html"
    path.write_text("<html>" + ("x" * 100) + "</html>")
    with pytest.raises(HtmlImportError, match="MB"):
        read_html_file(path)


def test_read_html_file_reads_real_valid_file(tmp_path):
    path = tmp_path / "card.html"
    path.write_text("<html><body>Hello {name}</body></html>")
    assert read_html_file(path) == "<html><body>Hello {name}</body></html>"


def test_import_html_file_strips_script_tags(tmp_path):
    path = tmp_path / "card.html"
    path.write_text(
        '<html><head><script>alert("x")</script></head>'
        '<body><h1>Deal</h1></body></html>'
    )
    result = import_html_file(path)
    assert "<script" not in result["html"]
    assert "alert" not in result["html"]
    assert "<h1>Deal</h1>" in result["html"]


def test_import_html_file_strips_inline_event_handlers(tmp_path):
    path = tmp_path / "card.html"
    path.write_text('<html><body><button onclick="doBad()">Click</button></body></html>')
    result = import_html_file(path)
    assert "onclick" not in result["html"]
    assert "<button" in result["html"]


def test_import_html_file_neutralizes_javascript_links(tmp_path):
    path = tmp_path / "card.html"
    path.write_text('<html><body><a href="javascript:evil()">Buy</a></body></html>')
    result = import_html_file(path)
    assert "javascript:" not in result["html"]


def test_import_html_file_preserves_variable_tokens_untouched(tmp_path):
    """The core requirement of ask #4: {name}/{amount}/etc tokens typed
    directly into a hand-authored HTML file must survive the sanitize step
    completely untouched, so per-recipient substitution still works exactly
    like it does on a Card-Creator-generated card."""
    path = tmp_path / "card.html"
    path.write_text(
        "<html><body><p>Hi {name}, your order of {amount} is ready "
        "on {date}.</p></body></html>"
    )
    result = import_html_file(path)
    assert "{name}" in result["html"]
    assert "{amount}" in result["html"]
    assert "{date}" in result["html"]


def test_extract_suggested_subject_prefers_title(tmp_path):
    html = "<html><head><title>50% Off Sale</title></head><body><h1>Different</h1></body></html>"
    assert extract_suggested_subject(html) == "50% Off Sale"


def test_extract_suggested_subject_falls_back_to_h1(tmp_path):
    html = "<html><body><h1>  Big   Launch  </h1></body></html>"
    assert extract_suggested_subject(html) == "Big Launch"


def test_extract_suggested_subject_empty_when_neither_present(tmp_path):
    html = "<html><body><p>No title or heading here.</p></body></html>"
    assert extract_suggested_subject(html) == ""


def test_import_html_file_extracts_subject_end_to_end(tmp_path):
    path = tmp_path / "card.html"
    path.write_text("<html><head><title>Launch Week</title></head><body>Hi</body></html>")
    result = import_html_file(path)
    assert result["subject"] == "Launch Week"


def test_inline_relative_images_embeds_a_real_local_image(tmp_path):
    """The real "fix broken references" requirement: a relative <img
    src="..."> pointing at a real file next to the imported HTML gets
    rewritten into a genuine, self-contained base64 data: URI."""
    png_bytes = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
    )
    (tmp_path / "logo.png").write_bytes(png_bytes)
    html = '<html><body><img src="logo.png"></body></html>'
    result = inline_relative_images(html, tmp_path)
    assert "data:image/png;base64," in result
    assert 'src="logo.png"' not in result


def test_inline_relative_images_leaves_remote_urls_untouched(tmp_path):
    html = '<html><body><img src="https://example.com/pic.png"></body></html>'
    result = inline_relative_images(html, tmp_path)
    assert result == html


def test_inline_relative_images_leaves_missing_local_file_untouched_not_crashing(tmp_path):
    """A broken relative reference in the source file is not this
    importer's fault to crash on -- the rest of a real card should still
    import successfully, just with that one reference left as-is."""
    html = '<html><body><img src="does_not_exist.png"></body></html>'
    result = inline_relative_images(html, tmp_path)
    assert result == html


def test_import_html_file_end_to_end_with_a_real_local_image(tmp_path):
    png_bytes = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
    )
    (tmp_path / "banner.png").write_bytes(png_bytes)
    path = tmp_path / "card.html"
    path.write_text(
        '<html><head><title>My Card</title></head>'
        '<body><img src="banner.png"><p>Hi {name}</p></body></html>'
    )
    result = import_html_file(path)
    assert "data:image/png;base64," in result["html"]
    assert "{name}" in result["html"]
    assert result["subject"] == "My Card"
    assert result["source_path"] == str(path)
