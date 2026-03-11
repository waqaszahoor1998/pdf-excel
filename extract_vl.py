#!/usr/bin/env python3
"""
PDF → extracted text/tables via a local vision-language model (Qwen2.5-VL-7B).

Flow:
  1. PDF pages are rendered to images (PyMuPDF). The model cannot read PDFs; it needs images.
  2. Each image is sent to Qwen2.5-VL together with a text PROMPT that tells the model
     how to format the output (e.g. "output tables with TAB-separated headers and rows").
  3. The model returns plain TEXT (not JSON). We parse that text (TAB/pipe-separated lines)
     into sections with name, headings, and rows.
  4. That structure is written as canonical JSON; run.py from-json + openpyxl then produce Excel.

So: PDF → images → [image + prompt] → model → text → our parser → JSON → Excel.
See docs/VL_PIPELINE_AND_LIBRARIES.md for libraries (PyMuPDF, pdfplumber, openpyxl) and details.

Requires: pip install -r requirements-vl.txt
          python scripts/download_qwen2vl.py  (once, to download model + mmproj)

Env: QWEN2VL_MODEL_DIR (default: ./models/qwen2.5-vl-7b) or QWEN2VL_MODEL_PATH + QWEN2VL_MMPROJ_PATH
"""

import base64
import json
import logging
import os
import re
import sys
from pathlib import Path

log = logging.getLogger(__name__)

# Default filenames from ggml-org/Qwen2.5-VL-7B-Instruct-GGUF
MODEL_FILENAME = "Qwen2.5-VL-7B-Instruct-Q4_K_M.gguf"
MMPROJ_FILENAME = "mmproj-Qwen2.5-VL-7B-Instruct-f16.gguf"

DEFAULT_PROMPT = "Extract all text and tables from this document page. Preserve structure: sections, headers, and rows. Output the content clearly."

# Prompt sent WITH each page image so the model knows how to format its reply.
# Section names should match standard report titles so we get QB-style sheet names (Net Assets, Operations, PLSummary, etc.).
TABLE_EXTRACTION_PROMPT = """Extract ONLY the data tables from this document page. Do not include disclaimers, page headers, footers, or non-table text.

For each table:
1. First line: the report or section title exactly as it appears, or use one of these when it matches: "Statement of Net Assets", "Statement of Operations", "Change in Partners' Capital", "MTD PNL Per Trading Account Summary", "Portfolio Activity", "Holdings", "Account Summary", "Journal Entry Import", "Journal Entries", "Unrealized Gains and Losses", "Changes in Accrued Dividend", "Changes in Accrued Interest", "Alt Inv Transfer", "Asset Allocation", "Tax Summary".
2. Second line: column headers separated by TAB (e.g. Account Name\tMarket Value\tCash In\tCash Out\tPNL\tMarket Value).
3. Following lines: one row per line, cells separated by TAB. You MUST include every value from the table: copy each number exactly as shown into the correct column (use 0 only when the source cell shows zero or is blank). Do not skip numeric cells or leave columns empty. Keep numbers as numbers (no currency symbols in the value). Preserve column alignment (same number of columns per row).

Use TAB character between columns. Output plain text only, no HTML or markdown. If there are no tables on this page, output: NO_TABLES"""


def _model_paths():
    """Resolve paths to main GGUF and mmproj from env."""
    root = Path(__file__).resolve().parent
    try:
        from dotenv import load_dotenv
        load_dotenv(root / ".env")
    except ImportError:
        pass

    model_path = os.environ.get("QWEN2VL_MODEL_PATH")
    mmproj_path = os.environ.get("QWEN2VL_MMPROJ_PATH")
    if model_path and mmproj_path:
        return Path(model_path).expanduser().resolve(), Path(mmproj_path).expanduser().resolve()

    model_dir = os.environ.get("QWEN2VL_MODEL_DIR")
    if not model_dir:
        model_dir = root / "models" / "qwen2.5-vl-7b"
    model_dir = Path(model_dir).expanduser().resolve()
    return model_dir / MODEL_FILENAME, model_dir / MMPROJ_FILENAME


def _ensure_cuda_path():
    """If llama-cpp-python was built with CUDA, its DLLs need CUDA runtime.
    The package uses CUDA_PATH for add_dll_directory(); set it before first import."""
    for candidate in (
        os.environ.get("CUDA_PATH"),
        r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v13.2",
        r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.8",
        r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.4",
    ):
        if not candidate:
            continue
        bin_dir = Path(candidate) / "bin"
        if bin_dir.exists():
            # Loader in llama_cpp uses CUDA_PATH for add_dll_directory(bin/lib)
            os.environ["CUDA_PATH"] = str(Path(candidate).resolve())
            path = os.environ.get("PATH", "")
            if str(bin_dir) not in path:
                os.environ["PATH"] = f"{bin_dir}{os.pathsep}{path}"
            break


def _load_llm():
    """Lazy-load the VL model and mmproj. Returns Llama instance."""
    _ensure_cuda_path()
    try:
        from llama_cpp import Llama
        from llama_cpp.llama_chat_format import Qwen25VLChatHandler
    except ImportError as e:
        raise ImportError(
            "Install VL dependencies: pip install -r requirements-vl.txt"
        ) from e

    model_path, mmproj_path = _model_paths()
    if not model_path.exists():
        raise FileNotFoundError(
            f"Model not found: {model_path}. Run: python scripts/download_qwen2vl.py"
        )
    if not mmproj_path.exists():
        raise FileNotFoundError(
            f"Mmproj not found: {mmproj_path}. Run: python scripts/download_qwen2vl.py"
        )

    log.info("Loading VL model %s and mmproj %s", model_path.name, mmproj_path.name)
    llm = Llama(
        model_path=str(model_path),
        mmproj=str(mmproj_path),
        n_ctx=4096,
        n_gpu_layers=-1,  # offload all to GPU if available
        verbose=False,
        chat_handler=Qwen25VLChatHandler(clip_model_path=str(mmproj_path), verbose=False),
    )
    return llm


def pdf_pages_to_images(pdf_path: str | Path, max_pages: int | None = None) -> list[bytes]:
    """
    Render PDF pages to PNG bytes. Uses PyMuPDF (fitz).
    Returns list of PNG image bytes, one per page (up to max_pages).
    """
    try:
        import fitz
    except ImportError:
        raise ImportError("PyMuPDF is required: pip install pymupdf") from None

    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {path}")

    doc = fitz.open(str(path))
    try:
        n = min(len(doc), max_pages) if max_pages else len(doc)
        images = []
        for i in range(n):
            page = doc[i]
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)  # 2x for readability
            images.append(pix.tobytes(output="png"))
        return images
    finally:
        doc.close()


def image_bytes_to_data_uri(png_bytes: bytes) -> str:
    """Encode PNG bytes as a data URI for the vision model."""
    b64 = base64.b64encode(png_bytes).decode("ascii")
    return f"data:image/png;base64,{b64}"


def run_vl_on_image(llm, image_data_uri: str, prompt: str = DEFAULT_PROMPT, max_tokens: int = 2048) -> str:
    """
    Run the VL model on one image and return the generated text.
    llm: Llama instance (with mmproj).
    """
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": image_data_uri}},
                {"type": "text", "text": prompt},
            ],
        }
    ]
    try:
        out = llm.create_chat_completion(
            messages=messages,
            max_tokens=max_tokens,
            temperature=0.1,
        )
    except Exception as e:
        log.warning("create_chat_completion failed (model may need different chat_format): %s", e)
        return ""
    choice = (out.get("choices") or [None])[0]
    if not choice:
        return ""
    msg = choice.get("message") or {}
    return (msg.get("content") or "").strip()


def extract_pdf_with_vl(
    pdf_path: str | Path,
    prompt: str = DEFAULT_PROMPT,
    max_pages: int | None = 10,
    llm=None,
) -> str:
    """
    Extract text from a PDF using the vision-language model: render pages to images,
    run VL on each, concatenate results. Use for scanned or low-text PDFs.

    Returns a single string with all extracted content (one block per page, separated).
    """
    images = pdf_pages_to_images(pdf_path, max_pages=max_pages)
    if not images:
        return ""

    if llm is None:
        llm = _load_llm()

    parts = []
    for i, png_bytes in enumerate(images):
        data_uri = image_bytes_to_data_uri(png_bytes)
        log.info("VL page %s/%s", i + 1, len(images))
        # prompt tells the model how to format output (e.g. TAB-separated tables) so we can parse it
        text = run_vl_on_image(llm, data_uri, prompt=prompt)
        if text:
            parts.append(f"--- Page {i + 1} ---\n{text}")
    return "\n\n".join(parts) if parts else ""


def _strip_html(line: str) -> str:
    """Remove simple HTML tags for cleaner parsing."""
    if not line or not isinstance(line, str):
        return ""
    s = line.strip()
    for tag in ("<p>", "</p>", "<html>", "</html>", "<body>", "</body>", "```html", "```"):
        s = s.replace(tag, "")
    return s.strip()


def _is_junk_line(line: str) -> bool:
    """Drop lines that are not useful table content."""
    s = line.strip()
    if not s or len(s) < 2:
        return True
    if s.upper() in ("NO_TABLES", "N/A"):
        return True
    # Page header/footer patterns
    if re.match(r"^Page\s+\d+\s+of\s+\d+$", s, re.I):
        return True
    if re.match(r"^\d+\s*$", s):  # lone number
        return True
    return False


def _parse_table_blocks(content: str) -> list[tuple[str, list[str], list[list[str]]]]:
    """
    Parse VL output into table blocks: (section_name, headers, rows).
    Expects tab-separated or pipe-separated lines; first line = title, second = header, rest = data.
    Returns list of (name, list of header cells, list of row cells).
    """
    blocks = []
    lines = [ln.strip() for ln in content.splitlines() if ln.strip()]
    if not lines:
        return blocks
    # Strip HTML from each line
    lines = [_strip_html(ln) for ln in lines if _strip_html(ln) and not _is_junk_line(ln)]
    if not lines:
        return blocks
    # Prefer TAB; fallback to pipe
    sep = "\t" if any("\t" in ln for ln in lines) else "|"
    i = 0
    while i < len(lines):
        line = lines[i]
        if _is_junk_line(line):
            i += 1
            continue
        parts = [p.strip() for p in line.split(sep) if p.strip()]
        if not parts:
            i += 1
            continue
        # One cell only: treat as possible section title; next line might be header
        if len(parts) == 1 and i + 1 < len(lines):
            next_line = lines[i + 1]
            next_parts = [p.strip() for p in next_line.split(sep) if p.strip()]
            if len(next_parts) >= 2:  # next line looks like header
                name = parts[0]
                headers = next_parts
                i += 2
                data_rows = []
                while i < len(lines):
                    row_parts = [p.strip() for p in lines[i].split(sep) if p.strip()]
                    if not row_parts:
                        i += 1
                        continue
                    if len(row_parts) == 1 and sep not in lines[i]:
                        break  # likely next section title
                    # Pad or trim to match header count
                    if len(row_parts) >= len(headers):
                        data_rows.append(row_parts[: len(headers)])
                    else:
                        data_rows.append(row_parts + [""] * (len(headers) - len(row_parts)))
                    i += 1
                if headers:
                    blocks.append((name, headers, data_rows))
                continue
        # This line has multiple columns: use as header, rest as data
        if len(parts) >= 2:
            name = "Table"
            headers = parts
            i += 1
            data_rows = []
            while i < len(lines):
                row_parts = [p.strip() for p in lines[i].split(sep) if p.strip()]
                if not row_parts:
                    i += 1
                    break
                if len(row_parts) == 1 and sep not in lines[i]:
                    break
                if len(row_parts) >= len(headers) - 1:
                    row = row_parts[: len(headers)] if len(row_parts) >= len(headers) else row_parts + [""] * (len(headers) - len(row_parts))
                    data_rows.append(row)
                i += 1
            if headers:
                blocks.append((name, headers, data_rows))
            continue
        i += 1
    return blocks


def _vl_text_to_sections(combined_text: str) -> list[dict]:
    """
    Split VL combined output (with "--- Page N ---" blocks) into sections
    in the project's JSON shape: { "name", "headings", "rows", "row_count", "column_count" }.
    Tries to parse table blocks (tab/pipe-separated) for proper headers and columns;
    otherwise one section per page with cleaned lines as rows.
    """
    sections = []
    pattern = re.compile(r"^--- Page (\d+) ---\s*$", re.MULTILINE)
    matches = list(pattern.finditer(combined_text))

    def add_section(name: str, headings: list, rows: list[list]) -> None:
        if not name and not headings and not rows:
            return
        sections.append({
            "name": name or "Section",
            "headings": headings,
            "rows": rows,
            "row_count": len(rows),
            "column_count": len(headings) if headings else (len(rows[0]) if rows else 0),
        })

    def process_content(content: str, page_label: str) -> None:
        content = content.strip()
        if not content:
            return
        # Try table blocks first (tab or pipe separated)
        blocks = _parse_table_blocks(content)
        if blocks:
            for name, headers, data_rows in blocks:
                add_section(name, headers, data_rows)
            return
        # Fallback: cleaned lines as single-column rows (no HTML, no junk)
        lines = []
        for ln in content.splitlines():
            cleaned = _strip_html(ln.strip())
            if cleaned and not _is_junk_line(cleaned):
                lines.append(cleaned)
        if lines:
            add_section(page_label, [], [[ln] for ln in lines])

    if not matches:
        process_content(combined_text.strip(), "Extracted")
        return sections
    for i, m in enumerate(matches):
        page_num = m.group(1)
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(combined_text)
        content = combined_text[start:end]
        process_content(content, f"Page {page_num}")
    return sections


def pdf_to_json_vl(
    pdf_path: str | Path,
    output_path: str | Path,
    prompt: str | None = None,
    max_pages: int | None = 10,
    llm=None,
) -> str:
    """
    Extract PDF with VL and write the project's canonical JSON format.
    Same schema as pdf_to_json (sections with name, headings, rows) so you can
    run: python run.py from-json <output.json> -o out.xlsx
    Uses table-focused prompt by default so output has proper headers and columns.
    """
    if prompt is None:
        prompt = TABLE_EXTRACTION_PROMPT
    text = extract_pdf_with_vl(pdf_path, prompt=prompt, max_pages=max_pages, llm=llm)
    sections = _vl_text_to_sections(text)
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {"sections": sections}
    with open(out, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    log.info("Wrote %d section(s) to %s", len(sections), out)
    return str(out)


def main():
    """CLI: python -m extract_vl <pdf_path> [--json FILE] [--out FILE] [--max-pages N]"""
    import argparse
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    parser = argparse.ArgumentParser(description="Extract content from PDF using Qwen2.5-VL (vision)")
    parser.add_argument("pdf_path", type=Path, help="Path to PDF")
    parser.add_argument("--prompt", default=None, help="Override prompt (default: table extraction for --json, generic for text)")
    parser.add_argument("--max-pages", type=int, default=10, help="Max pages to process (default 10)")
    parser.add_argument("--out", type=Path, default=None, help="Write raw text to file (default: stdout)")
    parser.add_argument("--json", type=Path, default=None, dest="json_path", help="Write canonical JSON (sections) to FILE; then use run.py from-json FILE -o out.xlsx")
    args = parser.parse_args()

    if not args.pdf_path.exists():
        print(f"Error: not found: {args.pdf_path}", file=sys.stderr)
        sys.exit(1)

    if args.json_path:
        result = pdf_to_json_vl(
            args.pdf_path,
            args.json_path,
            prompt=args.prompt,  # None => table extraction prompt
            max_pages=args.max_pages,
        )
        print(f"JSON: {result}")
    else:
        text = extract_pdf_with_vl(
            args.pdf_path,
            prompt=args.prompt or DEFAULT_PROMPT,
            max_pages=args.max_pages,
        )
        if args.out:
            args.out.write_text(text, encoding="utf-8")
            print(f"Wrote {args.out}")
        else:
            print(text)


if __name__ == "__main__":
    main()
