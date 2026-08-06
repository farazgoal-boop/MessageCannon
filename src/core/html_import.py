"""
Item 33 of the multi-product generalization pass: import an existing HTML
file — a card/landing-page snippet built elsewhere (exported previously
from Card Creator, hand-coded, or made in another tool) — and prepare it
for sending through the app's REAL send pipelines (the "Send as Visual
HTML Card" email mode already built for Card Creator, and a flattened
plain-text summary for WhatsApp), without needing to rebuild it in Card
Creator's own section-based builder.

Deliberately kept dependency-free of `src/ui` (this is `core/`, business
logic only) — image inlining reimplements the small, pure piece of
`card_creator_tab.image_file_to_data_uri` it needs rather than importing
across that boundary.
"""

from __future__ import annotations

import base64
import mimetypes
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Optional

# Generous for a real hand-built card/landing-page snippet, small enough
# that a genuinely wrong file (an entire multi-page site, a mistakenly
# selected huge file) is rejected with a clear reason instead of hanging
# the UI parsing something that was never meant to be a single email body.
MAX_IMPORT_HTML_BYTES = 2 * 1024 * 1024  # 2MB of raw HTML/CSS text

# Local images referenced by a relative path get inlined as base64 data:
# URIs (same reasoning as Card Creator's own uploads -- a standalone email/
# WhatsApp message can't rely on a relative file path resolving on the
# recipient's machine). Capped the same way to keep the final message a
# reasonable size to actually send.
MAX_INLINE_IMAGE_BYTES = 5 * 1024 * 1024


class HtmlImportError(Exception):
    """Raised for a file that can't be imported at all -- missing, too
    large, wrong extension, or empty. Always meant to be caught and shown
    to the user as a clear message, never left to surface as a traceback."""


def _strip_scripts_and_handlers(html: str) -> str:
    """Sanitizes imported HTML for safe use as an email/preview body:
    removes <script> blocks entirely (scripts don't run in real email
    clients or this app's own tkinterweb preview anyway, and stripping them
    removes any risk of them appearing as inert visible text if a client
    ever did render them), strips inline `on*="..."` event-handler
    attributes, and neutralizes any `javascript:` URI."""
    html = re.sub(r"(?is)<script\b[^>]*>.*?</script\s*>", "", html)
    html = re.sub(r"(?is)<script\b[^>]*/?>", "", html)
    # Inline event handlers: onclick="...", onload='...', etc.
    html = re.sub(r'(?i)\son\w+\s*=\s*"[^"]*"', "", html)
    html = re.sub(r"(?i)\son\w+\s*=\s*'[^']*'", "", html)
    html = re.sub(r'(?i)(href|src)\s*=\s*"javascript:[^"]*"', r'\1="#"', html)
    html = re.sub(r"(?i)(href|src)\s*=\s*'javascript:[^']*'", r"\1='#'", html)
    return html


def _guess_mime(path: Path) -> Optional[str]:
    mime_type, _ = mimetypes.guess_type(str(path))
    if mime_type and mime_type.startswith("image/"):
        return mime_type
    return None


def _inline_local_image(match: "re.Match[str]", base_dir: Path) -> str:
    """Regex-replacement callback for a single src="..." attribute value.
    Leaves absolute URLs (http(s)://) and already-inlined data: URIs
    completely alone -- only a genuinely relative/local path is resolved
    against the imported file's own directory and inlined. Any failure
    (file missing, too large, not a real image) leaves the original
    reference untouched rather than raising -- a broken relative reference
    in the source file is not this importer's fault to crash on, and the
    rest of a real card should still import successfully."""
    quote = match.group(1)
    src = match.group(2)
    if re.match(r"^(?:https?:|data:|//)", src, re.I):
        return match.group(0)
    candidate = (base_dir / src).resolve()
    try:
        if not candidate.is_file():
            return match.group(0)
        if candidate.stat().st_size > MAX_INLINE_IMAGE_BYTES:
            return match.group(0)
        mime_type = _guess_mime(candidate)
        if not mime_type:
            return match.group(0)
        encoded = base64.b64encode(candidate.read_bytes()).decode("ascii")
        return f'src={quote}data:{mime_type};base64,{encoded}{quote}'
    except OSError:
        return match.group(0)


def inline_relative_images(html: str, base_dir: Path) -> str:
    """Rewrites every relative <img src="..."> reference into a real,
    embedded base64 data: URI resolved against `base_dir` (the imported
    file's own directory) -- fixes the exact "broken references" problem a
    hand-authored HTML file commonly has once it leaves its original folder
    (an email/WhatsApp recipient has no access to the sender's filesystem).
    CSS `url(...)` backgrounds are intentionally left alone -- inlining
    those safely requires parsing full CSS, out of scope for this
    best-effort pass; a relative `url()` background simply won't render for
    the recipient, same as before this function ran."""
    pattern = re.compile(r'src=(["\'])([^"\']+)\1', re.I)
    return pattern.sub(lambda m: _inline_local_image(m, base_dir), html)


class _TitleExtractor(HTMLParser):
    """Pulls a sensible default subject line from imported HTML: prefers a
    real <title>, falls back to the first <h1>."""

    def __init__(self) -> None:
        super().__init__()
        self._in_title = False
        self._in_h1 = False
        self.title = ""
        self.h1 = ""

    def handle_starttag(self, tag, attrs):
        if tag == "title":
            self._in_title = True
        elif tag == "h1" and not self.h1:
            self._in_h1 = True

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        elif tag == "h1":
            self._in_h1 = False

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        elif self._in_h1:
            self.h1 += data


def extract_suggested_subject(html: str) -> str:
    parser = _TitleExtractor()
    try:
        parser.feed(html)
    except Exception:
        return ""
    text = (parser.title or parser.h1).strip()
    return re.sub(r"\s+", " ", text)


def read_html_file(path: Path) -> str:
    """Real file-level validation, before any parsing: exists, is a real
    .html/.htm file, isn't empty, and isn't suspiciously huge for a single
    message body."""
    if not path.is_file():
        raise HtmlImportError(f"File not found: {path}")
    if path.suffix.lower() not in (".html", ".htm"):
        raise HtmlImportError(
            f"\"{path.name}\" doesn't look like an HTML file (expected .html/.htm).")
    size = path.stat().st_size
    if size == 0:
        raise HtmlImportError(f"\"{path.name}\" is empty.")
    if size > MAX_IMPORT_HTML_BYTES:
        raise HtmlImportError(
            f"\"{path.name}\" is {size / (1024*1024):.1f}MB — please import a "
            f"single card/page snippet under {MAX_IMPORT_HTML_BYTES // (1024*1024)}MB.")
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        try:
            return path.read_text(encoding="latin-1")
        except Exception as exc:
            raise HtmlImportError(f"Couldn't read \"{path.name}\" as text: {exc}") from exc


def import_html_file(path: Path) -> dict:
    """The real end-to-end import: read -> sanitize -> inline local images
    -> suggest a subject. `{variable}` tokens already present in the source
    file (typed directly by whoever authored it, e.g. "{name}") pass
    through completely untouched -- generate_html-style substitution
    already treats braces as literal text, and this importer never escapes
    or rewrites them, so per-recipient personalization keeps working on an
    imported file exactly like it does on a Card-Creator-generated one.

    Returns {"html": sanitized+inlined HTML, "subject": suggested subject
    line (may be empty), "source_path": the resolved path}.
    """
    path = Path(path)
    raw = read_html_file(path)
    sanitized = _strip_scripts_and_handlers(raw)
    sanitized = inline_relative_images(sanitized, path.parent)
    subject = extract_suggested_subject(sanitized)
    return {"html": sanitized, "subject": subject, "source_path": str(path)}
