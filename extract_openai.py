#!/usr/bin/env python3
"""
PDF → Excel via OpenAI (ChatGPT) API.

Set OPENAI_API_KEY in .env. Get a key at https://platform.openai.com/api-keys
Uses extracted PDF text (no file upload) so it works with standard Chat Completions.
"""

import logging
import os
from pathlib import Path

import pdfplumber
from dotenv import load_dotenv

from extract import extract_csv_from_response, csv_to_excel, json_sections_to_excel
from extract_gemini import (
    SYSTEM_INSTRUCTION,
    SYSTEM_ORGANIZED_JSON,
    USER_ORGANIZED_JSON,
    extract_json_from_response,
)

load_dotenv()

log = logging.getLogger(__name__)

# Limit PDF text size to fit context (e.g. gpt-4o ~128k tokens; ~4 chars/token → ~100k chars safe)
MAX_PDF_TEXT_CHARS = 100_000


def _pdf_to_text(pdf_path: str) -> str:
    """Extract text from all pages. Truncate if too long."""
    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {path}")
    if path.suffix.lower() != ".pdf":
        raise ValueError("File must be a PDF")

    parts = []
    total = 0
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text and text.strip():
                if total + len(text) > MAX_PDF_TEXT_CHARS:
                    parts.append(text[: MAX_PDF_TEXT_CHARS - total] + "\n\n[Document truncated...]")
                    total = MAX_PDF_TEXT_CHARS
                    break
                parts.append(text)
                total += len(text)
    if not parts:
        raise ValueError("No text could be extracted from the PDF (empty or image-only).")
    return "\n\n".join(parts)


def extract_pdf_to_excel(
    pdf_path: str,
    user_query: str,
    output_path: str,
    api_key: str | None = None,
    model: str | None = None,
) -> str:
    """Ask AI: extract the requested part from the PDF (using extracted text) and save as Excel."""
    api_key = api_key or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("Set OPENAI_API_KEY in .env (https://platform.openai.com/api-keys)")
    model = model or os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

    text = _pdf_to_text(pdf_path)
    log.info("Calling OpenAI API (ask)…")

    try:
        from openai import OpenAI
    except ImportError:
        raise ImportError("Install the OpenAI SDK: pip install openai") from None

    client = OpenAI(api_key=api_key)
    user_content = f"Document text:\n\n{text}\n\n---\n\nExtract the following from this document and return only the CSV block as specified:\n\n{user_query}"

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_INSTRUCTION},
            {"role": "user", "content": user_content},
        ],
        max_tokens=8192,
    )
    reply = (response.choices[0].message.content or "").strip()
    if not reply:
        raise ValueError("OpenAI returned an empty response")

    csv_content = extract_csv_from_response(reply)
    csv_to_excel(csv_content, output_path)
    log.info("Done.")
    return output_path


def extract_pdf_to_organized_sections(
    pdf_path: str,
    api_key: str | None = None,
    model: str | None = None,
) -> list[dict]:
    """Organized: full PDF text → structured JSON (sections). Same interface as Gemini."""
    api_key = api_key or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("Set OPENAI_API_KEY in .env (https://platform.openai.com/api-keys)")
    model = model or os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

    text = _pdf_to_text(pdf_path)
    log.info("Calling OpenAI API (full document, organized)…")

    try:
        from openai import OpenAI
    except ImportError:
        raise ImportError("Install the OpenAI SDK: pip install openai") from None

    client = OpenAI(api_key=api_key)
    user_content = f"Document text:\n\n{text}\n\n---\n\n{USER_ORGANIZED_JSON}"

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_ORGANIZED_JSON},
            {"role": "user", "content": user_content},
        ],
        max_tokens=16384,
    )
    reply = (response.choices[0].message.content or "").strip()
    if not reply:
        raise ValueError("OpenAI returned an empty response")

    data = extract_json_from_response(reply)
    sections = data.get("sections")
    if not isinstance(sections, list):
        raise ValueError("Response has no 'sections' array")
    log.info("Extracted %d section(s).", len(sections))
    return sections
