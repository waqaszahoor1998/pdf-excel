#!/usr/bin/env python3
"""
PDF → Excel via Google Gemini API (free tier available).

Same as extract.py but uses Gemini instead of Anthropic.
Set GEMINI_API_KEY in .env. Get a free key at https://aistudio.google.com/app/apikey
"""

import logging
import os
from pathlib import Path

from dotenv import load_dotenv

from extract import extract_csv_from_response, csv_to_excel

load_dotenv()

log = logging.getLogger(__name__)

# Gemini allows larger files; we use 32 MB to match web app and keep behaviour consistent
MAX_PDF_BYTES = 32 * 1024 * 1024

SYSTEM_INSTRUCTION = """You are a precise data extraction assistant. You receive a PDF and a user request describing exactly which part of the document to extract (e.g. "company taxes for January 2026", "sales table from Q3").

Your ONLY job is to:
1. Find in the PDF the data that matches the user's request.
2. Return that data as a structured table.

You MUST respond with a valid CSV block and nothing else that could break parsing. Use this exact format:

---BEGIN CSV---
header1,header2,header3
value1,value2,value3
---END CSV---

Rules:
- First line is the header. Use clear, short names.
- Use comma as delimiter. If a value contains a comma, wrap the whole value in double quotes.
- No extra text outside the CSV block. Only the block between ---BEGIN CSV--- and ---END CSV---.
- If the requested data is not found, output a single-row CSV with column "error" and value "No matching data found".
"""


def extract_pdf_to_excel(
    pdf_path: str,
    user_query: str,
    output_path: str,
    api_key: str | None = None,
    model: str | None = None,
) -> str:
    """
    Extract data from PDF per user query using Gemini API and save as Excel.
    Returns the path to the saved Excel file.
    """
    api_key = api_key or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("Set GEMINI_API_KEY in .env or pass api_key=... (free at https://aistudio.google.com/app/apikey)")
    model = model or os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")

    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {path}")
    if path.suffix.lower() != ".pdf":
        raise ValueError("File must be a PDF")
    pdf_bytes = path.read_bytes()
    if len(pdf_bytes) > MAX_PDF_BYTES:
        raise ValueError(f"PDF too large (max {MAX_PDF_BYTES // (1024*1024)} MB)")

    try:
        from google import genai
        from google.genai import types
    except ImportError:
        raise ImportError("Install the Gemini SDK: pip install google-genai") from None

    log.info("Calling Gemini API…")
    client = genai.Client(api_key=api_key)

    user_prompt = f"Extract the following from this PDF and return only the CSV block as specified:\n\n{user_query}"

    response = client.models.generate_content(
        model=model,
        contents=[
            types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf"),
            user_prompt,
        ],
        config=types.GenerateContentConfig(
            system_instruction=[SYSTEM_INSTRUCTION],
        ),
    )

    # response.text in newer SDK; fallback for candidates
    if hasattr(response, "text") and response.text:
        text = response.text
    elif getattr(response, "candidates", None) and response.candidates:
        part = response.candidates[0].content.parts[0]
        text = part.text if hasattr(part, "text") else str(part)
    else:
        text = str(response)
    if not text:
        raise ValueError("Gemini returned an empty response")

    csv_content = extract_csv_from_response(text)
    csv_to_excel(csv_content, output_path)
    log.info("Done.")
    return output_path
