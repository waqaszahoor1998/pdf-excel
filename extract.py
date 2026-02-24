#!/usr/bin/env python3
"""
PDF → Excel via Anthropic (Claude) API.

Upload a PDF, ask in natural language what to extract (e.g. "taxes for January 2026"),
and get an Excel file with only that data.
"""

import argparse
import base64
import csv
import io
import logging
import os
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

import anthropic
from dotenv import load_dotenv
from openpyxl import Workbook

load_dotenv()

# Max PDF size ~32MB, 100 pages per Anthropic limits
MAX_PDF_BYTES = 32 * 1024 * 1024

EXTRACTION_SYSTEM_PROMPT = """You are a precise data extraction assistant. You receive a PDF and a user request describing exactly which part of the document to extract (e.g. "company taxes for January 2026", "sales table from Q3", "list of employees in the HR section").

Your ONLY job is to:
1. Find in the PDF the data that matches the user's request.
2. Return that data as a structured table. If there are multiple logical tables, return the one that best matches the request, or the first relevant one.

You MUST respond with a valid CSV block and nothing else that could break parsing. Use this exact format:

---BEGIN CSV---
header1,header2,header3
value1,value2,value3
...
---END CSV---

Rules:
- First line is the header (column names). Use clear, short names.
- Use comma as delimiter. If a value contains a comma, wrap the whole value in double quotes.
- No extra text, explanations, or markdown outside the CSV block. Only the block between ---BEGIN CSV--- and ---END CSV---.
- If the requested data is not found in the PDF, output a single-row CSV with a column "error" and value "No matching data found".
- Preserve numbers and dates as they appear; do not add units in the header unless they were in the document.
"""


def load_pdf_base64(path: str) -> str:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {path}")
    if path.suffix.lower() != ".pdf":
        raise ValueError("File must be a PDF")
    data = path.read_bytes()
    if len(data) > MAX_PDF_BYTES:
        raise ValueError(f"PDF too large (max {MAX_PDF_BYTES // (1024*1024)}MB)")
    return base64.standard_b64encode(data).decode("utf-8")


def extract_csv_from_response(text: str) -> str:
    s = text.strip()
    # Prefer our explicit block
    begin, end = "---BEGIN CSV---", "---END CSV---"
    i, j = s.find(begin), s.find(end)
    if i != -1 and j != -1 and j > i:
        return s[i + len(begin) : j].strip()
    # Fallback: markdown code block
    for marker in ("```csv", "```CSV", "```"):
        if marker in s:
            start = s.find(marker) + len(marker)
            rest = s[start:].strip()
            end_m = rest.find("```")
            if end_m != -1:
                return rest[:end_m].strip()
            return rest
    # Last resort: first line with commas as header, rest as rows
    lines = [ln.strip() for ln in s.splitlines() if ln.strip()]
    for k, line in enumerate(lines):
        if "," in line and k + 1 <= len(lines):
            return "\n".join(lines[k:])
    raise ValueError("No CSV block found in model response. Response was: " + text[:500])


def csv_to_excel(csv_content: str, out_path: str) -> None:
    reader = csv.reader(io.StringIO(csv_content))
    rows = list(reader)
    if not rows:
        raise ValueError("CSV has no rows")
    wb = Workbook()
    ws = wb.active
    ws.title = "Extracted"
    for r in rows:
        ws.append(r)
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    wb.save(out_path)


def extract_pdf_to_excel(
    pdf_path: str,
    user_query: str,
    output_path: str,
    api_key: str | None = None,
    model: str = "claude-sonnet-4-20250514",
) -> str:
    """
    Extract data from PDF per user query using Anthropic API and save as Excel.

    Returns the path to the saved Excel file.
    """
    api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("Set ANTHROPIC_API_KEY in .env or pass api_key=...")

    pdf_b64 = load_pdf_base64(pdf_path)
    log.info("Calling API…")
    client = anthropic.Anthropic(api_key=api_key)

    user_content = [
        {
            "type": "document",
            "source": {
                "type": "base64",
                "media_type": "application/pdf",
                "data": pdf_b64,
            },
        },
        {
            "type": "text",
            "text": f"Extract the following from this PDF and return only the CSV block as specified:\n\n{user_query}",
        },
    ]

    message = client.messages.create(
        model=model,
        max_tokens=8192,
        system=EXTRACTION_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_content}],
    )

    response_text = ""
    for block in message.content:
        if hasattr(block, "text"):
            response_text += block.text

    csv_content = extract_csv_from_response(response_text)
    csv_to_excel(csv_content, output_path)
    log.info("Done.")
    return output_path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Extract data from a PDF using a natural-language query and save to Excel (via Anthropic API)."
    )
    parser.add_argument("pdf", help="Path to the PDF file")
    parser.add_argument("query", help="What to extract, e.g. 'company taxes for January 2026'")
    parser.add_argument(
        "-o",
        "--output",
        default=None,
        help="Output Excel path (default: same name as PDF with .xlsx)",
    )
    parser.add_argument(
        "--model",
        default="claude-sonnet-4-20250514",
        help="Anthropic model (default: claude-sonnet-4-20250514)",
    )
    args = parser.parse_args()

    try:
        out = args.output or str(Path(args.pdf).with_suffix(".xlsx"))
        log.info("PDF: %s | Query: %s | Output: %s", args.pdf, args.query[:50] + "..." if len(args.query) > 50 else args.query, out)
        result = extract_pdf_to_excel(args.pdf, args.query, out, model=args.model)
        print(f"Saved: {result}")
        return 0
    except (FileNotFoundError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except anthropic.APIError as e:
        msg = str(e)
        if "authentication" in msg.lower() or "invalid_api_key" in msg.lower() or "401" in msg:
            print("Error: Invalid or missing API key. Set ANTHROPIC_API_KEY in .env.", file=sys.stderr)
        elif "rate" in msg.lower() or "429" in msg:
            print("Error: API rate limit exceeded. Try again later.", file=sys.stderr)
        elif "overloaded" in msg.lower() or "503" in msg:
            print("Error: API temporarily unavailable. Try again later.", file=sys.stderr)
        else:
            print(f"Error: API request failed. {msg}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
