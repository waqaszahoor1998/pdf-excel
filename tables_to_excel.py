#!/usr/bin/env python3
"""
PDF → Excel (no AI). Extract all tables from a PDF and write them to an Excel file.

Run this first to get started. Use extract.py later when you want AI to pick
only the data you ask for (e.g. "taxes for January 2026").
"""

import argparse
from pathlib import Path

import pdfplumber
from openpyxl import Workbook


def pdf_tables_to_excel(pdf_path: str, output_path: str | None = None) -> str:
    """
    Extract every table from the PDF and write to one Excel file.
    Each table becomes a sheet (Sheet1, Sheet2, ...). If a page has multiple
    tables, they are concatenated with a blank row between them.
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"Not found: {pdf_path}")
    if pdf_path.suffix.lower() != ".pdf":
        raise ValueError("File must be a .pdf")

    out = Path(output_path or pdf_path.with_suffix(".xlsx"))
    wb = Workbook()
    # Remove default sheet so we only have our named ones
    wb.remove(wb.active)

    with pdfplumber.open(pdf_path) as pdf:
        sheet_num = 0
        for page_num, page in enumerate(pdf.pages, start=1):
            tables = page.extract_tables()
            if not tables:
                continue
            for i, table in enumerate(tables):
                if not table:
                    continue
                sheet_num += 1
                name = f"Page{page_num}" if len(tables) == 1 else f"Page{page_num}_T{i+1}"
                # Excel sheet names: max 31 chars, no \ / * ? [ ]
                name = name.replace("\\", "").replace("/", "").replace("*", "").replace("?", "").replace("[", "").replace("]", "")[:31]
                ws = wb.create_sheet(title=name or f"Sheet{sheet_num}")
                for row in table:
                    ws.append([str(c).strip() if c is not None else "" for c in row])

    out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out)
    return str(out)


def main():
    parser = argparse.ArgumentParser(
        description="Extract all tables from a PDF into an Excel file (no API key required)."
    )
    parser.add_argument("pdf", help="Path to the PDF file")
    parser.add_argument("-o", "--output", default=None, help="Output .xlsx path")
    args = parser.parse_args()
    result = pdf_tables_to_excel(args.pdf, args.output)
    print(f"Saved: {result}")


if __name__ == "__main__":
    main()
