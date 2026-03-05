#!/usr/bin/env python3
"""
PDF → Excel via a small local language model (SmolLM), fully offline.

No API keys. Requires: pip install transformers torch (and optionally accelerate).
First run downloads the model (~700MB for 360M, ~3GB for 1.7B).

Flow: PDF → extract text locally (PyMuPDF) → SmolLM generates CSV/JSON from text + query → Excel.
SmolLM is text-only, so we do not send raw PDF bytes; we send extracted text.
"""

import json
import logging
import re
from pathlib import Path

from extract import extract_csv_from_response, csv_to_excel
from extract_gemini import extract_json_from_response

log = logging.getLogger(__name__)

# Max characters of PDF text to send to the model (context limit)
MAX_TEXT_CHARS = 24_000

SYSTEM_CSV = """You are a precise data extraction assistant. You receive extracted TEXT from a PDF and a user request.

Your ONLY job is to find in the text the data that matches the user's request and return it as a CSV.

You MUST respond with a valid CSV block and nothing else. Use this exact format:

---BEGIN CSV---
header1,header2,header3
value1,value2,value3
---END CSV---

Rules:
- First line is the header. Use clear, short names.
- Use comma as delimiter. If a value contains a comma, wrap the whole value in double quotes.
- No extra text outside the CSV block.
- If the requested data is not found, output a single-row CSV with column "error" and value "No matching data found"."""

USER_ORGANIZED_JSON = """Extract the entire content of the text below into structured JSON. Output a single JSON object with key "sections": an array of objects, each with "name" (string), "headers" (array of column headers), and "rows" (array of arrays, one per data row). One section per table or logical block. Include only what is in the text. Preserve every number and label. Output only the JSON, no markdown or explanation.

Text:
"""


def _pdf_to_text(pdf_path: str | Path, max_chars: int = MAX_TEXT_CHARS) -> str:
    """Extract plain text from PDF using PyMuPDF. Returns up to max_chars."""
    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {path}")
    if path.suffix.lower() != ".pdf":
        raise ValueError("File must be a PDF")

    try:
        import fitz
    except ImportError:
        raise ImportError("PyMuPDF is required for offline extraction: pip install pymupdf") from None

    doc = fitz.open(str(path))
    try:
        parts = []
        total = 0
        for page in doc:
            block = page.get_text("text", flags=fitz.TEXT_PRESERVE_WHITESPACE).strip()
            if block:
                if total + len(block) > max_chars:
                    parts.append(block[: max_chars - total])
                    total = max_chars
                    break
                parts.append(block)
                total += len(block)
        text = "\n\n".join(parts)
        if total >= max_chars:
            text += "\n\n[Text truncated for context limit.]"
        return text
    finally:
        doc.close()


def _load_smollm(model_name: str = "HuggingFaceTB/SmolLM2-360M-Instruct", device: str | None = None):
    """Lazy-load transformers and the model. Returns (model, tokenizer)."""
    try:
        from transformers import AutoModelForCausalLM, AutoTokenizer
    except ImportError:
        raise ImportError(
            "Install transformers and torch for offline SmolLM: pip install transformers torch"
        ) from None

    log.info("Loading %s (first run may download the model)…", model_name)
    tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(model_name, trust_remote_code=True)
    if device is None:
        try:
            import torch
            device = "cuda" if torch.cuda.is_available() else "cpu"
        except ImportError:
            device = "cpu"
    model = model.to(device)
    model.eval()
    return model, tokenizer, device


def _generate(
    prompt: str,
    system: str,
    model,
    tokenizer,
    device: str,
    max_new_tokens: int = 1024,
    temperature: float = 0.2,
) -> str:
    """Run one generation. Uses chat template if available."""
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": prompt},
    ]
    if hasattr(tokenizer, "apply_chat_template"):
        text = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )
    else:
        text = f"{system}\n\nUser: {prompt}\n\nAssistant:"
    inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=4096).to(device)
    import torch
    with torch.no_grad():
        out = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=temperature > 0,
            temperature=temperature if temperature > 0 else None,
            pad_token_id=tokenizer.eos_token_id,
        )
    response = tokenizer.decode(out[0][inputs["input_ids"].shape[1] :], skip_special_tokens=True)
    return response.strip()


def extract_pdf_to_excel(
    pdf_path: str,
    user_query: str,
    output_path: str,
    model_name: str = "HuggingFaceTB/SmolLM2-360M-Instruct",
    device: str | None = None,
    max_text_chars: int = MAX_TEXT_CHARS,
) -> str:
    """
    Extract data from PDF per user query using a local SmolLM (offline, no API key).
    PDF is converted to text locally; the model returns CSV from that text.
    """
    text = _pdf_to_text(pdf_path, max_chars=max_text_chars)
    if not text.strip():
        raise ValueError("No text could be extracted from the PDF")

    model, tokenizer, dev = _load_smollm(model_name=model_name, device=device)
    user_prompt = f"User request: {user_query}\n\nExtracted PDF text:\n{text}"
    log.info("Running SmolLM (offline)…")
    response = _generate(user_prompt, SYSTEM_CSV, model, tokenizer, dev)

    csv_content = extract_csv_from_response(response)
    csv_to_excel(csv_content, output_path)
    log.info("Saved: %s", output_path)
    return output_path


def extract_pdf_to_organized_sections(
    pdf_path: str,
    model_name: str = "HuggingFaceTB/SmolLM2-360M-Instruct",
    device: str | None = None,
    max_text_chars: int = MAX_TEXT_CHARS,
) -> list[dict]:
    """
    Extract full PDF content into structured JSON sections using local SmolLM (offline).
    Returns list of section dicts (name, headers, rows) for use with json_sections_to_excel.
    """
    text = _pdf_to_text(pdf_path, max_chars=max_text_chars)
    if not text.strip():
        raise ValueError("No text could be extracted from the PDF")

    model, tokenizer, dev = _load_smollm(model_name=model_name, device=device)
    prompt = USER_ORGANIZED_JSON + text
    log.info("Running SmolLM (offline) for full-doc structure…")
    response = _generate(prompt, "You output only valid JSON. No markdown, no explanation.", model, tokenizer, dev, max_new_tokens=2048)

    data = extract_json_from_response(response)
    sections = data.get("sections") or []
    return sections


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Extract data from PDF using local SmolLM (offline).")
    parser.add_argument("pdf", help="Path to PDF")
    parser.add_argument("query", help="What to extract, e.g. 'all tables' or 'summary'")
    parser.add_argument("-o", "--output", default=None, help="Output Excel path")
    parser.add_argument("--model", default="HuggingFaceTB/SmolLM2-360M-Instruct", help="HuggingFace model name")
    parser.add_argument("--device", default=None, help="Device: cpu or cuda")
    args = parser.parse_args()
    out = args.output or str(Path(args.pdf).with_suffix(".xlsx"))
    try:
        extract_pdf_to_excel(args.pdf, args.query, out, model_name=args.model, device=args.device or None)
        return 0
    except Exception as e:
        log.exception("%s", e)
        return 1


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    sys.exit(main())
