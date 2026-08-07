"""Renders docs/user_manual_content.py's structured CONTENT into two real,
shareable files:

  docs/getting_started_guide.md            -- plain Markdown, easy to read/
                                               edit/diff in the repo
  docs/MessageCannon_Pro_User_Manual.pdf   -- the actual PDF deliverable,
                                               built with reportlab (already
                                               a project dependency, see
                                               requirements.txt)

Run: python scripts/build_user_manual.py
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from docs.user_manual_content import (  # noqa: E402
    CONTENT, MANUAL_SUBTITLE, MANUAL_SUPPORT_EMAIL, MANUAL_TITLE, MANUAL_VERSION,
)

MD_PATH = PROJECT_ROOT / "docs" / "getting_started_guide.md"
PDF_PATH = PROJECT_ROOT / "docs" / "MessageCannon_Pro_User_Manual.pdf"


def render_markdown() -> str:
    lines = [
        f"# {MANUAL_TITLE} — {MANUAL_SUBTITLE}",
        "",
        f"Version {MANUAL_VERSION} · Support: {MANUAL_SUPPORT_EMAIL} · "
        f"Generated {date.today().isoformat()}",
        "",
        "> **A note on screenshots:** this guide is written to be followed "
        "with the real app open next to it. Sections marked \"📸 Screenshot "
        "needed\" describe exactly what to capture — those images weren't "
        "captured automatically for this pass (see the top of "
        "`docs/user_manual_content.py` for why), so Faraz should add his "
        "own screenshot for each one before sharing this guide externally. "
        "The Tour Mode section is the one exception — it reuses a real, "
        "already-safety-reviewed screenshot from that feature's own demo.",
        "",
        "---",
        "",
    ]
    for kind, payload in CONTENT:
        if kind == "h1":
            lines.append(f"## {payload}")
            lines.append("")
        elif kind == "h2":
            lines.append(f"### {payload}")
            lines.append("")
        elif kind == "p":
            lines.append(payload)
            lines.append("")
        elif kind == "ul":
            for item in payload:
                lines.append(f"- {item}")
            lines.append("")
        elif kind == "ol":
            for index, item in enumerate(payload, start=1):
                lines.append(f"{index}. {item}")
            lines.append("")
        elif kind == "table":
            header, *rows = payload
            lines.append("| " + " | ".join(header) + " |")
            lines.append("|" + "|".join(["---"] * len(header)) + "|")
            for row in rows:
                lines.append("| " + " | ".join(row) + " |")
            lines.append("")
        elif kind == "shot":
            lines.append(f"> 📸 **Screenshot needed:** {payload}")
            lines.append("")
        elif kind == "image":
            rel_path, caption = payload
            lines.append(f"![{caption}]({rel_path})")
            lines.append("")
            lines.append(f"*{caption}*")
            lines.append("")
        elif kind == "note":
            lines.append(f"> 💡 **Tip:** {payload}")
            lines.append("")
        elif kind == "warn":
            lines.append(f"> ⚠️ **Caution:** {payload}")
            lines.append("")
        elif kind == "pagebreak":
            lines.append("---")
            lines.append("")
        else:
            raise ValueError(f"Unknown block kind: {kind!r}")
    return "\n".join(lines)


def render_pdf() -> None:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import LETTER
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import (
        HRFlowable, Image, ListFlowable, ListItem, PageBreak, Paragraph,
        SimpleDocTemplate, Spacer, Table, TableStyle,
    )

    ACCENT = colors.HexColor("#6366F1")
    TEXT_HEAD = colors.HexColor("#12161C")
    TEXT_MUTED = colors.HexColor("#5B6570")
    BADGE_BG = colors.HexColor("#EEF1F6")
    WARN_BG = colors.HexColor("#FDEDED")
    WARN_BORDER = colors.HexColor("#EF4444")
    NOTE_BORDER = colors.HexColor("#6366F1")
    SHOT_BG = colors.HexColor("#F3EAD8")
    SHOT_BORDER = colors.HexColor("#B5651D")

    base = getSampleStyleSheet()
    style_h1 = ParagraphStyle("MCH1", parent=base["Heading1"], textColor=ACCENT,
                               fontSize=18, spaceBefore=18, spaceAfter=10)
    style_h2 = ParagraphStyle("MCH2", parent=base["Heading2"], textColor=TEXT_HEAD,
                               fontSize=13, spaceBefore=12, spaceAfter=6)
    style_p = ParagraphStyle("MCP", parent=base["BodyText"], textColor=TEXT_HEAD,
                              fontSize=10.3, leading=15, spaceAfter=8)
    style_li = ParagraphStyle("MCLI", parent=style_p, spaceAfter=3)
    style_callout = ParagraphStyle("MCCallout", parent=style_p, fontSize=9.8,
                                    leading=14, spaceAfter=0)
    style_title = ParagraphStyle("MCTitle", parent=base["Title"], textColor=TEXT_HEAD,
                                  fontSize=30, spaceAfter=6)
    style_subtitle = ParagraphStyle("MCSubtitle", parent=base["Normal"],
                                     textColor=ACCENT, fontSize=15,
                                     alignment=1, spaceAfter=4)
    style_meta = ParagraphStyle("MCMeta", parent=base["Normal"],
                                 textColor=TEXT_MUTED, fontSize=9.5,
                                 alignment=1)
    style_caption = ParagraphStyle("MCCaption", parent=base["Normal"],
                                    textColor=TEXT_MUTED, fontSize=9,
                                    alignment=1, spaceAfter=10)

    story = []
    story.append(Spacer(1, 2.2 * inch))
    story.append(Paragraph(MANUAL_TITLE, ParagraphStyle(
        "MCCoverTitle", parent=style_title, alignment=1, fontSize=32)))
    story.append(Paragraph(MANUAL_SUBTITLE, style_subtitle))
    story.append(Spacer(1, 0.3 * inch))
    story.append(HRFlowable(width="40%", thickness=1.4, color=ACCENT,
                             hAlign="CENTER", spaceAfter=14))
    story.append(Paragraph(
        f"Version {MANUAL_VERSION} &nbsp;·&nbsp; Support: {MANUAL_SUPPORT_EMAIL}",
        style_meta))
    story.append(Paragraph(f"Generated {date.today().strftime('%B %d, %Y')}", style_meta))
    story.append(PageBreak())

    def callout(text: str, bg, border, icon: str, label: str):
        table = Table(
            [[Paragraph(f"<b>{icon} {label}</b> {text}", style_callout)]],
            colWidths=[6.3 * inch],
        )
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), bg),
            ("BOX", (0, 0), (-1, -1), 1, border),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ]))
        return table

    for kind, payload in CONTENT:
        if kind == "h1":
            story.append(Paragraph(payload, style_h1))
            story.append(HRFlowable(width="100%", thickness=0.7,
                                     color=BADGE_BG, spaceAfter=8))
        elif kind == "h2":
            story.append(Paragraph(payload, style_h2))
        elif kind == "p":
            story.append(Paragraph(payload, style_p))
        elif kind == "ul":
            story.append(ListFlowable(
                [ListItem(Paragraph(item, style_li)) for item in payload],
                bulletType="bullet", start="circle", leftIndent=16))
            story.append(Spacer(1, 8))
        elif kind == "ol":
            story.append(ListFlowable(
                [ListItem(Paragraph(item, style_li)) for item in payload],
                bulletType="1", leftIndent=16))
            story.append(Spacer(1, 8))
        elif kind == "table":
            header, *rows = payload
            wrapped = [[Paragraph(f"<b>{cell}</b>", style_callout) for cell in header]]
            for row in rows:
                wrapped.append([Paragraph(cell, style_callout) for cell in row])
            col_count = len(header)
            col_width = 6.3 * inch / col_count
            table = Table(wrapped, colWidths=[col_width] * col_count, repeatRows=1)
            table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), ACCENT),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.6, BADGE_BG),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, BADGE_BG]),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]))
            story.append(table)
            story.append(Spacer(1, 10))
        elif kind == "shot":
            story.append(callout(payload, SHOT_BG, SHOT_BORDER,
                                  "📸", "Screenshot needed:"))
            story.append(Spacer(1, 10))
        elif kind == "image":
            rel_path, caption = payload
            img_path = PROJECT_ROOT / "docs" / rel_path
            from PIL import Image as PILImage
            with PILImage.open(img_path) as pil_img:
                px_w, px_h = pil_img.size
            max_w = 6.3 * inch
            max_h = 4.2 * inch
            scale = min(max_w / px_w, max_h / px_h)
            story.append(Image(str(img_path), width=px_w * scale, height=px_h * scale))
            story.append(Spacer(1, 4))
            story.append(Paragraph(caption, style_caption))
        elif kind == "note":
            story.append(callout(payload, BADGE_BG, NOTE_BORDER, "💡", "Tip:"))
            story.append(Spacer(1, 10))
        elif kind == "warn":
            story.append(callout(payload, WARN_BG, WARN_BORDER, "⚠️", "Caution:"))
            story.append(Spacer(1, 10))
        elif kind == "pagebreak":
            story.append(PageBreak())
        else:
            raise ValueError(f"Unknown block kind: {kind!r}")

    doc = SimpleDocTemplate(
        str(PDF_PATH), pagesize=LETTER,
        leftMargin=0.85 * inch, rightMargin=0.85 * inch,
        topMargin=0.75 * inch, bottomMargin=0.75 * inch,
        title=f"{MANUAL_TITLE} — {MANUAL_SUBTITLE}", author="Muhammad Faraz",
    )
    doc.build(story)


def main() -> None:
    MD_PATH.write_text(render_markdown(), encoding="utf-8")
    render_pdf()
    print(f"Wrote {MD_PATH}")
    print(f"Wrote {PDF_PATH}")


if __name__ == "__main__":
    main()
