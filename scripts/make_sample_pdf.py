#!/usr/bin/env python3
"""Generate a sample PDF with tables for testing the PDF → Excel converter.
   Run from project root: python scripts/make_sample_pdf.py
   Creates sample_report.pdf in the project root."""

from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

# Output next to script's parent (project root)
root = Path(__file__).resolve().parent.parent
out_path = root / "sample_report.pdf"

doc = SimpleDocTemplate(str(out_path), pagesize=letter)
story = []
styles = getSampleStyleSheet()

# Title
story.append(Paragraph("Sample Report for PDF→Excel Test", styles["Title"]))
story.append(Spacer(1, 20))

# Table 1: Simple data
data1 = [
    ["Product", "Qty", "Price", "Total"],
    ["Widget A", "10", "2.50", "25.00"],
    ["Widget B", "5", "4.00", "20.00"],
    ["Widget C", "8", "1.75", "14.00"],
]
t1 = Table(data1)
t1.setStyle(TableStyle([
    ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 10),
    ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
    ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.black),
    ("BOX", (0, 0), (-1, -1), 0.5, colors.black),
]))
story.append(t1)
story.append(Spacer(1, 30))

# Table 2: Another section
data2 = [
    ["Month", "Revenue", "Expenses"],
    ["January 2026", "12,500", "8,200"],
    ["February 2026", "14,200", "9,100"],
]
t2 = Table(data2)
t2.setStyle(TableStyle([
    ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 10),
    ("BACKGROUND", (0, 0), (-1, 0), colors.lightblue),
    ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.black),
    ("BOX", (0, 0), (-1, -1), 0.5, colors.black),
]))
story.append(t2)

doc.build(story)
print(f"Created: {out_path}")
