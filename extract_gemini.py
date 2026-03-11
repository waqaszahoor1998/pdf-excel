#!/usr/bin/env python3
"""
PDF → Excel via Google Gemini API (free tier available).

Same as extract.py but uses Gemini instead of Anthropic.
Set GEMINI_API_KEY in .env. Get a free key at https://aistudio.google.com/app/apikey
"""

import json
import logging
import os
import re
from pathlib import Path

from dotenv import load_dotenv

from extract import extract_csv_from_response, csv_to_excel, json_sections_to_excel

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

# Organized extraction: full PDF → structured JSON (sections with name, headers, rows). We then convert to Excel or return JSON.
SYSTEM_ORGANIZED_JSON = """You are an expert at extracting document content exactly as it appears. You receive a PDF (e.g. bank statement, report). Your job is to EXTRACT what is there—do not generate or add anything.
1. Read the ENTIRE document.
2. Identify real sections and tables (e.g. Account Summary, detail tables).
3. Output ONLY a single JSON object with this shape (no other text):
{"sections": [{"name": "Section title", "headers": ["Col1","Col2",...], "rows": [["a","b"],...]}, ...]}
Rules: EXTRACT ONLY. One section per table or logical block. Preserve every number and label exactly. Do not add calculations. Output only the JSON."""

USER_ORGANIZED_JSON = """Extract the entire content of this PDF into structured JSON. Output a single JSON object with key "sections": an array of objects, each with "name" (string), "headers" (array of column headers), and "rows" (array of arrays, one per data row). One section per table or logical block. Neat and readable. Include only what is in the PDF. Preserve every number and label exactly. Output only the JSON, no markdown or explanation."""


def extract_json_from_response(text: str) -> dict:
    """Find JSON in model response (```json ... ``` or raw { ... }) and return parsed dict."""
    text = (text or "").strip()
    code_block = re.search(r"```(?:json)?\s*\n?([\s\S]*?)```", text)
    if code_block:
        raw = code_block.group(1).strip()
        start = raw.find("{")
        if start != -1:
            depth = 0
            for i in range(start, len(raw)):
                if raw[i] == "{":
                    depth += 1
                elif raw[i] == "}":
                    depth -= 1
                    if depth == 0:
                        return json.loads(raw[start : i + 1])
    start = text.find('{"sections"')
    if start == -1:
        start = text.find("{")
    if start != -1:
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    return json.loads(text[start : i + 1])
    raise ValueError("No valid JSON object found in response")


def extract_pdf_to_organized_sections(
    pdf_path: str,
    api_key: str | None = None,
    model: str | None = None,
) -> list[dict]:
    """
    Send the full PDF to Gemini; AI returns structured JSON. Parse and return list of sections
    (each: name, headers, rows). Use this to write Excel via json_sections_to_excel or save as JSON.
    """
    api_key = api_key or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("Set GEMINI_API_KEY in .env (free at https://aistudio.google.com/app/apikey)")
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

    log.info("Calling Gemini API (full document, organized)…")
    client = genai.Client(api_key=api_key)

    response = client.models.generate_content(
        model=model,
        contents=[
            types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf"),
            USER_ORGANIZED_JSON,
        ],
        config=types.GenerateContentConfig(
            system_instruction=[SYSTEM_ORGANIZED_JSON],
        ),
    )

    if hasattr(response, "text") and response.text:
        text = response.text
    elif getattr(response, "candidates", None) and response.candidates:
        part = response.candidates[0].content.parts[0]
        text = part.text if hasattr(part, "text") else str(part)
    else:
        text = str(response)
    if not text:
        raise ValueError("Gemini returned an empty response")

    data = extract_json_from_response(text)
    sections = data.get("sections")
    if not isinstance(sections, list):
        raise ValueError("JSON has no 'sections' array or it is not a list")
    log.info("Extracted %d section(s).", len(sections))
    return sections


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
