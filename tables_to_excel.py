#!/usr/bin/env python3
"""
PDF → Excel (no AI). Extract all tables from a PDF and write them to an Excel file.

Part of the converter foundation. Use extract.py for the AI agent (natural-language extraction).
"""

import argparse
import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

import pdfplumber
from openpyxl import Workbook


def pdf_tables_to_excel(
    pdf_path: str,
    output_path: str | None = None,
    overwrite: bool = True,
) -> str:
    """
    Extract every table from the PDF and write to one Excel file.
    Each table becomes a sheet. If no tables are found, writes one sheet with a message.
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"Not found: {pdf_path}")
    if pdf_path.suffix.lower() != ".pdf":
        raise ValueError("File must be a .pdf")

    out = Path(output_path or pdf_path.with_suffix(".xlsx"))
    if out.exists() and not overwrite:
        raise FileExistsError(f"Output exists (use --overwrite to replace): {out}")

    out.parent.mkdir(parents=True, exist_ok=True)
    wb = Workbook()
    wb.remove(wb.active)

    try:
        with pdfplumber.open(pdf_path) as pdf:
            total_pages = len(pdf.pages)
            sheet_num = 0
            for page_num, page in enumerate(pdf.pages, start=1):
                if total_pages > 1:
                    log.info("Page %d/%d", page_num, total_pages)
                tables = page.extract_tables()
                if not tables:
                    continue
                for i, table in enumerate(tables):
                    if not table:
                        continue
                    sheet_num += 1
                    name = f"Page{page_num}" if len(tables) == 1 else f"Page{page_num}_T{i+1}"
                    name = name.replace("\\", "").replace("/", "").replace("*", "").replace("?", "").replace("[", "").replace("]", "")[:31]
                    ws = wb.create_sheet(title=name or f"Sheet{sheet_num}")
                    for row in table:
                        ws.append([str(c).strip() if c is not None else "" for c in row])

            if sheet_num == 0:
                ws = wb.create_sheet(title="Info")
                ws.append(["No tables detected in this PDF."])
    except Exception as e:
        msg = str(e).lower()
        if "password" in msg or "encrypted" in msg:
            raise ValueError("PDF appears password-protected or encrypted; not supported.") from e
        if "invalid" in msg or "cannot read" in msg or "failed" in msg:
            raise ValueError("PDF could not be read (corrupt or invalid file).") from e
        raise

    wb.save(out)
    log.info("Wrote %d sheet(s) to %s", sheet_num if sheet_num > 0 else 1, out)
    return str(out)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Extract all tables from a PDF into an Excel file (no API key required)."
    )
    parser.add_argument("pdf", help="Path to the PDF file")
    parser.add_argument("-o", "--output", default=None, help="Output .xlsx path")
    parser.add_argument("--no-overwrite", action="store_false", dest="overwrite", default=True, help="Do not overwrite; fail if output file already exists")
    args = parser.parse_args()

    try:
        log.info("Input: %s", args.pdf)
        result = pdf_tables_to_excel(args.pdf, args.output, overwrite=args.overwrite)
        print(f"Saved: {result}")
        return 0
    except (FileNotFoundError, ValueError, FileExistsError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
