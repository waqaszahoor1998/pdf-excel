#!/usr/bin/env python3
"""
Build docs/WORKFLOWS_AND_COMMANDS.pdf from docs/WORKFLOWS_AND_COMMANDS.md (ReportLab).
Run: python scripts/generate_workflows_report_pdf.py [-o path.pdf]
"""

from __future__ import annotations

import argparse
import re
from datetime import date
from pathlib import Path


def _escape_xml(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _bold_md(s: str) -> str:
    s = _escape_xml(s)
    while "**" in s:
        a = s.find("**")
        b = s.find("**", a + 2)
        if b == -1:
            break
        inner = s[a + 2 : b]
        s = s[:a] + "<b>" + inner + "</b>" + s[b + 2 :]
    return s


def main() -> int:
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.units import inch
        from reportlab.platypus import (
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            Table,
            TableStyle,
        )
    except ImportError as e:
        raise SystemExit(f"reportlab required: {e}") from e

    root = Path(__file__).resolve().parent.parent
    md_path = root / "docs" / "WORKFLOWS_AND_COMMANDS.md"

    ap = argparse.ArgumentParser()
    ap.add_argument(
        "-o",
        "--output",
        default=str(root / "output" / "Workflows_and_Commands_Report.pdf"),
        help="Output PDF path",
    )
    args = ap.parse_args()
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    text = md_path.read_text(encoding="utf-8")
    lines = [ln.rstrip() for ln in text.splitlines()]

    styles = getSampleStyleSheet()
    story = []
    story.append(
        Paragraph(
            f"<b>PDF–Excel tool — workflows reference</b><br/>"
            f"<i>pdf-excel v3.2 · {date.today().isoformat()}</i>",
            styles["Title"],
        )
    )
    story.append(Spacer(1, 14))

    i = 0
    while i < len(lines):
        ln = lines[i]
        if not ln.strip():
            story.append(Spacer(1, 6))
            i += 1
            continue

        # Markdown table block
        if ln.strip().startswith("|") and "|" in ln[1:]:
            rows_raw: list[list[str]] = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                row = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                # skip separator |---|---|
                if row and not re.match(r"^[\s\-:|]+$", "".join(row)):
                    rows_raw.append(row)
                i += 1
            if rows_raw:
                data = [[Paragraph(_bold_md(c or " "), styles["BodyText"]) for c in r] for r in rows_raw]
                t = Table(data, colWidths=[2.2 * inch, 4.3 * inch])
                t.setStyle(
                    TableStyle(
                        [
                            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8eef5")),
                            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                            ("VALIGN", (0, 0), (-1, -1), "TOP"),
                            ("LEFTPADDING", (0, 0), (-1, -1), 6),
                            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                            ("TOPPADDING", (0, 0), (-1, -1), 4),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                        ]
                    )
                )
                story.append(t)
                story.append(Spacer(1, 10))
            continue

        if ln.startswith("# "):
            story.append(Paragraph(_bold_md(ln[2:].strip()), styles["Title"]))
            story.append(Spacer(1, 10))
        elif ln.startswith("## "):
            story.append(Spacer(1, 8))
            story.append(Paragraph(_bold_md(ln[3:].strip()), styles["Heading2"]))
            story.append(Spacer(1, 6))
        elif ln.startswith("### "):
            story.append(Spacer(1, 6))
            story.append(Paragraph(_bold_md(ln[4:].strip()), styles["Heading3"]))
            story.append(Spacer(1, 4))
        elif ln.lstrip().startswith("- "):
            story.append(Paragraph("• " + _bold_md(ln.strip()[2:].strip()), styles["BodyText"]))
        elif ln.strip().startswith("**") and ":**" in ln:
            story.append(Paragraph(_bold_md(ln.strip()), styles["BodyText"]))
        else:
            story.append(Paragraph(_bold_md(ln), styles["BodyText"]))
        i += 1

    doc = SimpleDocTemplate(
        str(out_path),
        pagesize=letter,
        title="Workflows and Commands",
        author="pdf-excel",
    )
    doc.build(story)
    print(f"Saved: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
