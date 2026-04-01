#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path


def main() -> int:
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    except Exception as e:
        raise SystemExit(f"reportlab not available: {e}")

    root = Path(__file__).resolve().parent.parent
    md_path = root / "docs" / "REPORT.md"
    out_path = root / "docs" / "REPORT.pdf"

    text = md_path.read_text(encoding="utf-8")
    # Minimal markdown-ish to paragraphs: keep headings and bullets readable.
    lines = [ln.rstrip() for ln in text.splitlines()]

    styles = getSampleStyleSheet()
    story = []

    for ln in lines:
        if not ln.strip():
            story.append(Spacer(1, 10))
            continue
        if ln.startswith("# "):
            story.append(Paragraph(f"<b>{ln[2:].strip()}</b>", styles["Title"]))
            story.append(Spacer(1, 10))
            continue
        if ln.startswith("## "):
            story.append(Spacer(1, 6))
            story.append(Paragraph(f"<b>{ln[3:].strip()}</b>", styles["Heading2"]))
            story.append(Spacer(1, 6))
            continue
        if ln.startswith("### "):
            story.append(Spacer(1, 4))
            story.append(Paragraph(f"<b>{ln[4:].strip()}</b>", styles["Heading3"]))
            story.append(Spacer(1, 4))
            continue
        if ln.lstrip().startswith("- "):
            bullet = ln.strip()[2:].strip()
            story.append(Paragraph(f"• {bullet}", styles["BodyText"]))
            continue
        # Bold markers **text** -> <b>text</b> (simple, non-nested)
        s = ln.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        while "**" in s:
            a = s.find("**")
            b = s.find("**", a + 2)
            if b == -1:
                break
            inner = s[a + 2 : b]
            s = s[:a] + "<b>" + inner + "</b>" + s[b + 2 :]
        story.append(Paragraph(s, styles["BodyText"]))

    doc = SimpleDocTemplate(str(out_path), pagesize=letter, title="Report")
    doc.build(story)
    print(f"Saved PDF: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

