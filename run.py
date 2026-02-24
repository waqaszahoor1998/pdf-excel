#!/usr/bin/env python3
"""
Single entry point for PDF → Excel.

  python run.py tables <pdf> [pdf2 ...]   Extract all tables (no AI). Batch: multiple PDFs → multiple Excel files.
  python run.py ask <pdf> <query>         AI agent: extract what you ask for. Optional: multiple PDFs with same query.
"""

import argparse
import sys
from pathlib import Path

# Project modules
from tables_to_excel import pdf_tables_to_excel
from extract import extract_pdf_to_excel
import anthropic


def _expand_pdfs(paths):
    """Expand paths to a list of .pdf files. If a path is a dir, add its .pdf children."""
    out = []
    for p in paths:
        path = Path(p)
        if not path.exists():
            raise FileNotFoundError(f"Not found: {path}")
        if path.is_file():
            if path.suffix.lower() == ".pdf":
                out.append(path)
            else:
                raise ValueError(f"Not a PDF: {path}")
        else:
            for f in sorted(path.glob("*.pdf")):
                out.append(f)
    return out


def cmd_tables(args) -> int:
    overwrite = not args.no_overwrite
    pdfs = _expand_pdfs(args.pdfs)
    if not pdfs:
        print("Error: No PDF files found.", file=sys.stderr)
        return 1
    if args.output and len(pdfs) > 1:
        print("Error: -o/--output only allowed for a single PDF.", file=sys.stderr)
        return 1
    for i, pdf in enumerate(pdfs):
        out = args.output if len(pdfs) == 1 and args.output else None
        if len(pdfs) > 1:
            print(f"[{i+1}/{len(pdfs)}] {pdf}")
        try:
            result = pdf_tables_to_excel(str(pdf), out, overwrite=overwrite)
            print(f"Saved: {result}")
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
    return 0


def cmd_ask(args) -> int:
    pdfs = _expand_pdfs(args.pdf)
    if not pdfs:
        print("Error: No PDF files found.", file=sys.stderr)
        return 1
    if args.output and len(pdfs) > 1:
        print("Error: -o/--output only allowed for a single PDF.", file=sys.stderr)
        return 1
    for i, pdf in enumerate(pdfs):
        out = args.output
        if not out and len(pdfs) == 1:
            out = str(Path(pdf).with_suffix(".xlsx"))
        elif not out:
            out = str(Path(pdf).with_suffix(".xlsx"))
        if len(pdfs) > 1:
            print(f"[{i+1}/{len(pdfs)}] {pdf}")
        try:
            result = extract_pdf_to_excel(str(pdf), args.query, out, model=args.model)
            print(f"Saved: {result}")
        except anthropic.APIError as e:
            msg = str(e).lower()
            if "401" in msg or "auth" in msg:
                print("Error: Invalid or missing API key. Set ANTHROPIC_API_KEY in .env.", file=sys.stderr)
            elif "429" in msg or "rate" in msg:
                print("Error: API rate limit exceeded. Try again later.", file=sys.stderr)
            else:
                print(f"Error: API request failed. {e}", file=sys.stderr)
            return 1
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="PDF → Excel: extract tables (offline) or ask the AI agent for specific data.",
        epilog="Examples:\n  %(prog)s tables report.pdf\n  %(prog)s tables a.pdf b.pdf\n  %(prog)s ask report.pdf \"taxes for January 2026\"",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="cmd", required=True, help="Command")

    # tables: one or more PDFs
    p_tables = sub.add_parser("tables", help="Extract all tables from PDF(s) to Excel (no AI)")
    p_tables.add_argument("pdfs", nargs="+", help="PDF file(s) or directory containing PDFs")
    p_tables.add_argument("-o", "--output", default=None, help="Output .xlsx path (single PDF only)")
    p_tables.add_argument("--no-overwrite", action="store_true", help="Do not overwrite existing output")
    p_tables.set_defaults(func=cmd_tables)

    # ask: PDF(s) + query
    p_ask = sub.add_parser("ask", help="AI agent: extract what you ask for from PDF(s)")
    p_ask.add_argument("pdf", nargs="+", help="PDF file(s) or directory containing PDFs")
    p_ask.add_argument("query", help="What to extract, e.g. 'company taxes for January 2026'")
    p_ask.add_argument("-o", "--output", default=None, help="Output .xlsx path (single PDF only)")
    p_ask.add_argument("--model", default="claude-sonnet-4-20250514", help="Anthropic model")
    p_ask.set_defaults(func=cmd_ask)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
