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
import time
from pathlib import Path

log = logging.getLogger(__name__)

# Default filenames from ggml-org/Qwen2.5-VL-7B-Instruct-GGUF
MODEL_FILENAME = "Qwen2.5-VL-7B-Instruct-Q4_K_M.gguf"
MMPROJ_FILENAME = "mmproj-Qwen2.5-VL-7B-Instruct-f16.gguf"

DEFAULT_PROMPT = "Extract all text and tables from this document page. Preserve structure: sections, headers, and rows. Output the content clearly."

# Prompt sent WITH each page image so the model knows how to format its reply.
# UNIVERSAL: no assumed document type or section names; use for any PDF (invoices, reports, statements, etc.).
UNIVERSAL_EXTRACTION_PROMPT = """Extract every data table on this document page. The document can be any type (invoice, report, statement, form, etc.).

For EACH table:
1. First line: the section or table title exactly as it appears in the document (e.g. a heading above the table). If there is no clear title, use a short description like "Table 1" or the first header text.
2. Second line: column headers only, separated by TAB (one TAB between each header).
3. Next lines: one data row per line. Same number of columns as the header. Use TAB between cells. Copy every value exactly as shown; keep numbers and dates as printed (commas allowed, no currency symbols in numeric cells). Include all rows: data rows and any total/subtotal rows.

Rules:
- Use TAB between columns. Output plain text only, no HTML or markdown. Do not repeat the same phrase in every cell.
- If the table has ROW LABELS (e.g. "Current Month", "Current Year" as row names), keep that structure: first column = row labels, remaining columns = data. Do NOT turn those labels into column headers for a single row.
- If the page has both a dollar summary (e.g. Beginning Market Value, Net Deposits, Investment Results, Ending Market Value) and a separate percentage table (e.g. Current Month %, Year to Date %, Inception to Date %), output them as TWO separate tables with distinct titles (e.g. "Performance Summary" and "Performance (%)").
- Leave cells EMPTY when they are blank in the document. Do NOT copy values from other rows to fill blanks. If unsure, leave empty.
If there are no tables on this page, output: NO_TABLES"""

# Generic (legacy): like universal but with examples of common report section names.
TABLE_EXTRACTION_PROMPT = """Extract ONLY the data tables from this document page. Do not include disclaimers, page headers, footers, or non-table text.

For each table:
1. First line: the report or section title exactly as it appears, or use one of these when it matches: "Statement of Net Assets", "Statement of Operations", "Change in Partners' Capital", "MTD PNL Per Trading Account Summary", "Portfolio Activity", "Holdings", "Account Summary", "Journal Entry Import", "Journal Entries", "Unrealized Gains and Losses", "Changes in Accrued Dividend", "Changes in Accrued Interest", "Alt Inv Transfer", "Asset Allocation", "Tax Summary".
2. Second line: column headers separated by TAB (e.g. Account Name\tMarket Value\tCash In\tCash Out\tPNL\tMarket Value).
3. Following lines: one row per line, cells separated by TAB. You MUST include every value from the table: copy each number exactly as shown into the correct column (use 0 only when the source cell shows zero or is blank). Do not skip numeric cells or leave columns empty. Keep numbers as numbers (no currency symbols in the value). Preserve column alignment (same number of columns per row).

Use TAB character between columns. Output plain text only, no HTML or markdown. If there are no tables on this page, output: NO_TABLES"""

# Prompt profiles: broker statements (GS, Morgan Stanley, etc.), tax statements, generic.
BROKER_STATEMENT_PROMPT = """Extract ALL data tables from this broker or portfolio statement page. Use TAB character between every column. Ignore disclaimers and long footer text.

Rules:
1. For EACH distinct table or section, output:
   - First line: section title (e.g. "Portfolio Information", "Portfolio Activity", "Holdings", "Reportable Income", "Investment Results", "Performance Summary", "Performance (%)", "US Tax Summary", "General Information").
   - Second line: column headers only, separated by TAB (e.g. Beginning Market Value\tNet Deposits (Withdrawals)\tInvestment Results\tEnding Market Value).
   - Next lines: one data row per line. First cell = row label; remaining cells = values in same order as headers. Use TAB between cells. Include every row: detail rows AND total/subtotal rows.

2. OVERVIEW PAGE (page with Portfolio Activity, Investment Results, Performance): You MUST extract every table on this page. Output: Portfolio Activity (all 5 rows: market value dates, interest received, dividends received, change, ending value), Investment Results (Current Month and Current Year rows with 4 columns each), Performance Summary (one row), then Performance (%) (Name and three percentage columns). Do not skip the Overview page or merge its tables into one.

3. Preserve table structure: when the document has row labels (e.g. "Current Month", "Current Year"), keep them as the FIRST COLUMN of data rows, with the numeric columns as the other columns. Do NOT turn row labels into column headers so that you output only one row of numbers.

4. Investment Results: output as one table with headers "Beginning Market Value", "Net Deposits (Withdrawals)", "Investment Results", "Ending Market Value" (or as shown). Two data rows: first row label "Current Month" with its four values; second row label "Current Year" with its four values.

5. Performance: output TWO separate tables. (a) "Performance Summary" or "Performance": one row with Beginning Market Value, Net Deposits, Investment Results, Ending Market Value. (b) "Performance (%)": headers "Name", "Current Month (%)", "Year to Date (%)", "Inception to Date (%)"; one row per strategy/benchmark with name in first column and three percentage values. Do NOT merge these into one wide table.

6. US Tax Summary / Reportable Income: Reportable Interest must contain ONLY these rows: Corporate Interest, Non-US Interest, Bank Interest, Total Reportable Interest, Total Reportable Income. Copy every value exactly (e.g. Non-US Interest Current Month, Quarter to Date, Year to date as shown). Do NOT add rows from Dividends (e.g. Qualified Foreign Dividends) into the Reportable Interest table. When the page shows NON-REPORTABLE ITEMS or Accrued Interest Paid at Purchase, output a separate table with that title and all rows (e.g. Interest Paid on Other Securities, totals) with Current Month, Quarter to Date, Year to date columns.

7. US Tax Summary (Continued) / Realized and Unrealized: For LONG TERM REALIZED GAIN (LOSS), TOTAL REALIZED CAPITAL GAINS, and CURRENT UNREALIZED GAIN (LOSS), include ALL three columns (Current Month, Quarter to Date, Year to date) for every row. Do not leave Year to date empty when it has a value in the document.

8. If a row has BLANK cells in the document, leave those cells BLANK. Do NOT copy values from the next or previous row. Empty means empty.

9. Numbers: copy exactly as printed (keep commas). No currency symbols in numeric cells. Same number of columns per row as the header. Output each table exactly once. Use TAB between columns. Plain text only. If no tables, output: NO_TABLES"""

TAX_STATEMENT_PROMPT = """Extract ALL data tables from this tax or financial statement page. Use TAB character between every column. Ignore disclaimers.

Rules:
1. For each table: first line = section title (e.g. "US Tax Summary", "Dividends and Distributions", "Reportable Interest", "Non-Reportable Items"). Second line = column headers only (e.g. Current Month\tQuarter to Date\tYear to date). Then one row per line: row label in first column, values in remaining columns, TAB-separated.

2. On US Tax Summary pages output separate tables in this order: "Dividends and Distributions" (Qualified US, Non-Qualified US, Qualified Foreign, Non-Qualified Foreign, TOTAL), "Reportable Interest" (Corporate Interest, Non-US Interest, Bank Interest, TOTAL only—do not add dividend rows here), "Total Reportable Income", then "Non-Reportable Items" or "Accrued Interest Paid at Purchase" with same three columns and all rows (e.g. Interest Paid on Other Securities, totals). Include every total and subtotal row.

3. For Realized Capital Gains and Unrealized Gain (Loss): include ALL three columns (Current Month, Quarter to Date, Year to date) for every row; do not omit Year to date when present. Copy each value exactly.

4. Output each table exactly once. Do not repeat the same phrase in every cell. Preserve numbers exactly (including parentheses for negatives). Same column count in every row. Use TAB between columns. Plain text only. If no tables, output: NO_TABLES"""

PROMPT_PROFILES = {
    "generic": TABLE_EXTRACTION_PROMPT,
    "universal": UNIVERSAL_EXTRACTION_PROMPT,  # Any PDF type; no assumed structure. Use as default for unknown documents.
    "broker_statement": BROKER_STATEMENT_PROMPT,
    "tax_statement": TAX_STATEMENT_PROMPT,
}


def _load_vl_config() -> dict:
    """Load VL config from config/vl.json and env overrides."""
    root = Path(__file__).resolve().parent
    config_path = root / "config" / "vl.json"
    cfg = {}
    if config_path.exists():
        try:
            with open(config_path, encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception as e:
            log.warning("Could not load %s: %s", config_path, e)
    # Env overrides
    if os.environ.get("VL_MAX_TOKENS"):
        try:
            cfg["max_tokens"] = int(os.environ["VL_MAX_TOKENS"])
        except ValueError:
            pass
    if os.environ.get("VL_IMAGE_SCALE"):
        try:
            cfg["image_scale"] = float(os.environ["VL_IMAGE_SCALE"])
        except ValueError:
            pass
    if os.environ.get("VL_MAX_PAGES_PER_RUN"):
        try:
            cfg["max_vl_pages_per_run"] = int(os.environ["VL_MAX_PAGES_PER_RUN"])
        except ValueError:
            pass
    return cfg


def _parse_page_ranges(spec: str) -> list[int]:
    """Parse '1-5,10-20' into [1,2,3,4,5,10,11,...,20] (1-based, sorted, unique)."""
    out = []
    for part in spec.strip().split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            try:
                lo, hi = int(a.strip()), int(b.strip())
                for p in range(lo, hi + 1):
                    if p > 0:
                        out.append(p)
            except ValueError:
                continue
        else:
            try:
                p = int(part)
                if p > 0:
                    out.append(p)
            except ValueError:
                continue
    return sorted(dict.fromkeys(out))


def _get_prompt_for_schema(schema_type: str) -> str:
    """Return prompt for schema_type (universal, generic, broker_statement, tax_statement)."""
    return PROMPT_PROFILES.get(schema_type.lower(), UNIVERSAL_EXTRACTION_PROMPT)


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

    cfg = _load_vl_config()
    n_ctx = int(cfg.get("n_ctx") or cfg.get("context_length") or 4096)
    n_batch = int(cfg.get("n_batch") or 512)
    log.info("Loading VL model %s and mmproj %s (n_ctx=%s)", model_path.name, mmproj_path.name, n_ctx)
    llm = Llama(
        model_path=str(model_path),
        mmproj=str(mmproj_path),
        n_ctx=n_ctx,
        n_batch=n_batch,
        n_gpu_layers=-1,  # offload all to GPU if available
        verbose=False,
        chat_handler=Qwen25VLChatHandler(clip_model_path=str(mmproj_path), verbose=False),
    )
    return llm


# Keywords used to auto-detect document type from first page(s) text. No user selection needed.
DOC_TYPE_TAX_PHRASES = [
    "us tax summary", "tax summary", "reportable income", "dividends and distributions",
    "qualified us dividends", "non-qualified us dividends", "reportable interest",
    "non-reportable items", "accrued interest paid at purchase", "form 1099", "1099-",
]
DOC_TYPE_BROKER_PHRASES = [
    "portfolio information", "portfolio activity", "statement of net assets",
    "statement of operations", "holdings", "investment results", "account statement",
    "broker", "market value as of", "change in market value", "asset allocation",
]


def detect_document_type(pdf_path: str | Path, max_pages_to_scan: int = 2) -> str:
    """
    Auto-detect document type from PDF text (first 1–2 pages). No user selection required.
    Returns: "tax_statement", "broker_statement", or "universal".
    """
    try:
        import fitz
    except ImportError:
        return "universal"
    path = Path(pdf_path)
    if not path.exists():
        return "universal"
    try:
        doc = fitz.open(str(path))
        text_parts = []
        for i in range(min(max_pages_to_scan, len(doc))):
            text_parts.append(doc[i].get_text("text"))
        doc.close()
    except Exception:
        return "universal"
    combined = " ".join(text_parts).lower()
    tax_score = sum(1 for p in DOC_TYPE_TAX_PHRASES if p in combined)
    broker_score = sum(1 for p in DOC_TYPE_BROKER_PHRASES if p in combined)
    if tax_score > broker_score:
        log.info("Auto-detected document type: tax_statement (score %d vs %d)", tax_score, broker_score)
        return "tax_statement"
    if broker_score > tax_score:
        log.info("Auto-detected document type: broker_statement (score %d vs %d)", broker_score, tax_score)
        return "broker_statement"
    log.info("Auto-detected document type: universal (no strong tax/broker signal)")
    return "universal"


def pdf_pages_to_images(
    pdf_path: str | Path,
    max_pages: int | None = None,
    page_ranges: list[int] | None = None,
    scale: float = 2.0,
) -> list[tuple[int, bytes]]:
    """
    Render PDF pages to PNG bytes. Uses PyMuPDF (fitz).
    Returns list of (1-based_page_number, png_bytes).
    If page_ranges is set (e.g. [1,2,3,5,10]), only those 1-based pages are rendered.
    When both page_ranges and max_pages are set, only pages in page_ranges with page <= max_pages are rendered.
    Otherwise renders first max_pages pages. scale: 2.0 = 2x resolution (faster), 3.0 = 3x (clearer).
    """
    try:
        import fitz
    except ImportError:
        raise ImportError("PyMuPDF is required: pip install pymupdf") from None

    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {path}")

    doc = fitz.open(str(path))
    total_pages = len(doc)
    try:
        if page_ranges:
            pages = [p for p in page_ranges if 1 <= p <= total_pages]
            if max_pages is not None:
                pages = [p for p in pages if p <= max_pages]
            indices = [p - 1 for p in pages]
        else:
            n = min(total_pages, max_pages) if max_pages else total_pages
            indices = list(range(n))
        matrix = fitz.Matrix(scale, scale)
        images = []
        for i in indices:
            page = doc[i]
            pix = page.get_pixmap(matrix=matrix, alpha=False)
            images.append((i + 1, pix.tobytes(output="png")))
        return images
    finally:
        doc.close()


def image_bytes_to_data_uri(png_bytes: bytes) -> str:
    """Encode PNG bytes as a data URI for the vision model."""
    b64 = base64.b64encode(png_bytes).decode("ascii")
    return f"data:image/png;base64,{b64}"


def _image_to_png_bytes(image_input: str | Path | bytes) -> bytes:
    """Convert path, bytes, or PIL Image to PNG bytes for the VL model."""
    if isinstance(image_input, bytes):
        return image_input
    path = Path(image_input)
    if path.exists():
        raw = path.read_bytes()
        # If already PNG, return as-is; else try PIL to convert
        if raw[:8] == b"\x89PNG\r\n\x1a\n":
            return raw
        try:
            from PIL import Image
            img = Image.open(path).convert("RGB")
            buf = __import__("io").BytesIO()
            img.save(buf, format="PNG")
            return buf.getvalue()
        except Exception:
            return raw
    raise FileNotFoundError(f"Image not found: {path}")


def extract_single_image_to_sections(
    image_input: str | Path | bytes,
    prompt: str | None = None,
    schema_type: str | None = None,
    llm=None,
    max_tokens: int | None = None,
    temperature: float | None = None,
) -> list[dict]:
    """
    Run VL on a single image (path, bytes, or PIL Image) and return parsed sections.
    Used by benchmark scripts to evaluate on dataset images without creating PDFs.
    """
    if hasattr(image_input, "save"):  # PIL Image
        import io
        buf = io.BytesIO()
        if getattr(image_input, "mode", "") == "RGBA":
            image_input.convert("RGB").save(buf, format="PNG")
        else:
            image_input.save(buf, format="PNG")
        png_bytes = buf.getvalue()
    else:
        png_bytes = _image_to_png_bytes(image_input)
    data_uri = image_bytes_to_data_uri(png_bytes)
    if prompt is None:
        prompt = _get_prompt_for_schema(schema_type or _load_vl_config().get("schema_type_default", "universal"))
    if llm is None:
        llm = _load_llm()
    cfg = _load_vl_config()
    tokens = max_tokens if max_tokens is not None else cfg.get("max_tokens", 4096)
    temp = temperature if temperature is not None else cfg.get("temperature", 0.1)
    text = run_vl_on_image(llm, data_uri, prompt=prompt, max_tokens=tokens, temperature=temp)
    sections = _vl_text_to_sections(text)
    sections = _normalize_sections(sections)
    sections = _drop_repetitive_sections(sections)
    sections = _split_performance_sections(sections)
    sections = _clear_duplicate_data_in_consecutive_rows(sections)
    return sections


def run_vl_on_image(
    llm,
    image_data_uri: str,
    prompt: str = DEFAULT_PROMPT,
    max_tokens: int = 2048,
    temperature: float = 0.1,
) -> str:
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
            temperature=temperature,
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
    page_ranges: list[int] | None = None,
    image_scale: float | None = None,
    max_tokens: int | None = None,
    max_vl_pages_per_run: int | None = None,
    temperature: float | None = None,
) -> tuple[str, dict]:
    """
    Extract text from a PDF using the vision-language model: render pages to images,
    run VL on each, concatenate results. Use for scanned or low-text PDFs.

    Returns (combined_text, meta_dict). meta_dict has: per_page_seconds, page_numbers, total_seconds.
    """
    cfg = _load_vl_config()
    scale = image_scale if image_scale is not None else cfg.get("image_scale", 2.0)
    tokens = max_tokens if max_tokens is not None else cfg.get("max_tokens", 2048)
    temp = temperature if temperature is not None else cfg.get("temperature", 0.1)
    cap = max_vl_pages_per_run if max_vl_pages_per_run is not None else cfg.get("max_vl_pages_per_run", 100)

    images = pdf_pages_to_images(pdf_path, max_pages=max_pages, page_ranges=page_ranges, scale=scale)
    if not images:
        return "", {"per_page_seconds": [], "page_numbers": [], "total_seconds": 0.0}

    # Cap number of pages sent to VL
    if len(images) > cap:
        log.info("Capping VL to first %s pages (max_vl_pages_per_run)", cap)
        images = images[:cap]

    if llm is None:
        llm = _load_llm()
        log.info("VL using GPU (n_gpu_layers=-1)")

    parts = []
    page_times = []
    page_numbers = []
    for i, (page_num, png_bytes) in enumerate(images):
        # Reset KV cache before each page to avoid "failed to find a memory slot" (llama_decode returned 1)
        if hasattr(llm, "reset"):
            try:
                llm.reset()
            except Exception:
                pass
        data_uri = image_bytes_to_data_uri(png_bytes)
        t0 = time.perf_counter()
        text = run_vl_on_image(llm, data_uri, prompt=prompt, max_tokens=tokens, temperature=temp)
        elapsed = time.perf_counter() - t0
        page_times.append(elapsed)
        page_numbers.append(page_num)
        log.info("VL page %s/%s (page %s) (%.1f s)", i + 1, len(images), page_num, elapsed)
        if text:
            parts.append(f"--- Page {page_num} ---\n{text}")
    total = sum(page_times)
    if page_times:
        avg = total / len(page_times)
        log.info("VL timing: total %.1f s, %.1f s/page (GPU)", total, avg)
    meta = {
        "per_page_seconds": page_times,
        "page_numbers": page_numbers,
        "total_seconds": round(total, 2),
    }
    return "\n\n".join(parts) if parts else "", meta


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


def _split_line_to_cells(line: str, sep: str) -> list[str]:
    """Split a line into cells by sep; if sep is TAB and line has no TAB, try splitting on 2+ spaces."""
    parts = [p.strip() for p in line.split(sep) if p.strip()]
    if len(parts) == 1 and sep == "\t" and "\t" not in line:
        # Model used spaces instead of TABs; split on 2+ spaces for column alignment
        parts = [p.strip() for p in re.split(r"\s{2,}", line) if p.strip()]
    return parts


def _parse_table_blocks(content: str) -> list[tuple[str, list[str], list[list[str]]]]:
    """
    Parse VL output into table blocks: (section_name, headers, rows).
    Expects tab-separated or pipe-separated lines; first line = title, second = header, rest = data.
    If no TABs, tries splitting on 2+ spaces for table-like lines. Returns list of (name, list of header cells, list of row cells).
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
        parts = _split_line_to_cells(line, sep)
        if not parts:
            i += 1
            continue
        # One cell only: treat as possible section title; next line might be header
        if len(parts) == 1 and i + 1 < len(lines):
            next_line = lines[i + 1]
            next_parts = _split_line_to_cells(next_line, sep)
            if len(next_parts) >= 2:  # next line looks like header
                name = parts[0]
                headers = next_parts
                i += 2
                data_rows = []
                while i < len(lines):
                    row_parts = _split_line_to_cells(lines[i], sep)
                    if not row_parts:
                        i += 1
                        continue
                    if len(row_parts) == 1 and sep not in lines[i] and not re.search(r"\s{2,}", lines[i]):
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
                row_parts = _split_line_to_cells(lines[i], sep)
                if not row_parts:
                    i += 1
                    break
                if len(row_parts) == 1 and sep not in lines[i] and not re.search(r"\s{2,}", lines[i]):
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
    in the project's JSON shape: { "name", "headings", "rows", "row_count", "column_count", "page" }.
    Tries to parse table blocks (tab/pipe-separated) for proper headers and columns;
    otherwise one section per page with cleaned lines as rows.
    """
    sections = []
    pattern = re.compile(r"^--- Page (\d+) ---\s*$", re.MULTILINE)
    matches = list(pattern.finditer(combined_text))

    def add_section(name: str, headings: list, rows: list[list], page: int | None = None) -> None:
        if not name and not headings and not rows:
            return
        sec = {
            "name": name or "Section",
            "headings": headings,
            "rows": rows,
            "row_count": len(rows),
            "column_count": len(headings) if headings else (len(rows[0]) if rows else 0),
        }
        if page is not None:
            sec["page"] = page
        sections.append(sec)

    def process_content(content: str, page_label: str, page_num: int | None = None) -> None:
        content = content.strip()
        if not content:
            return
        # Try table blocks first (tab or pipe separated)
        blocks = _parse_table_blocks(content)
        if blocks:
            for name, headers, data_rows in blocks:
                add_section(name, headers, data_rows, page=page_num)
            return
        # Fallback: cleaned lines as single-column rows (no HTML, no junk)
        lines = []
        for ln in content.splitlines():
            cleaned = _strip_html(ln.strip())
            if cleaned and not _is_junk_line(cleaned):
                lines.append(cleaned)
        if lines:
            add_section(page_label, [], [[ln] for ln in lines], page=page_num)

    if not matches:
        process_content(combined_text.strip(), "Extracted", page_num=None)
        return sections
    for i, m in enumerate(matches):
        page_num = int(m.group(1))
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(combined_text)
        content = combined_text[start:end]
        process_content(content, f"Page {page_num}", page_num=page_num)
    return sections


def _row_normalized(row) -> tuple:
    """Normalize a row to a tuple of stripped strings for comparison."""
    if not isinstance(row, (list, tuple)):
        return (str(row).strip(),)
    return tuple(str(c).strip() if c is not None else "" for c in row)


# When comparing with PDF: if the repeated phrase appears more than this many times on the page, we do NOT collapse/drop (treat as real data).
REPEAT_PDF_COUNT_THRESHOLD = 10


def pdf_phrase_count_for_file(pdf_path: str | Path):
    """
    Return a callable (page_num: int, phrase: str) -> int that counts how many times
    phrase appears in the text of that PDF page (1-based page_num). Used so we only
    collapse/drop repetitive sections when the PDF confirms the phrase is rare on that page.
    """
    try:
        import fitz
    except ImportError:
        return None
    path = Path(pdf_path)
    if not path.exists():
        return None
    page_text_cache = {}
    count_cache = {}

    def count(page_num: int, phrase: str) -> int:
        if not phrase or page_num < 1:
            return 0
        key = (int(page_num), phrase)
        if key in count_cache:
            return count_cache[key]
        try:
            if page_num not in page_text_cache:
                doc = fitz.open(str(path))
                try:
                    if page_num <= len(doc):
                        page_text_cache[page_num] = (doc[page_num - 1].get_text() or "").upper()
                    else:
                        page_text_cache[page_num] = ""
                finally:
                    doc.close()
            text = page_text_cache.get(page_num, "")
            n = text.count(phrase.upper())
            count_cache[key] = n
            return n
        except Exception:
            count_cache[key] = 0
            return 0

    return count


def _drop_repetitive_sections(
    sections: list[dict],
    pdf_phrase_count=None,
) -> list[dict]:
    """
    Remove or fix sections where the model repeated the same content (e.g. same phrase in every cell).
    - If all rows in a section are identical (or 90%+ match first row), keep only the first row.
    - If a section ends up with one row and every cell in that row is the same value, drop the section (garbage).
    - Headings that are all the same repeated value are normalized to a single sensible header when possible.

    When pdf_phrase_count(page_num, phrase) is provided: we only collapse or drop when the phrase appears
    at most REPEAT_PDF_COUNT_THRESHOLD times on that page in the PDF. If it appears more often, we assume
    the repetition is real data and leave the section unchanged.
    """
    out = []
    for sec in sections:
        sec = dict(sec)
        rows = list(sec.get("rows") or [])
        headings = sec.get("headings") or []
        if not rows:
            out.append(sec)
            continue
        # Normalize for comparison
        first_norm = _row_normalized(rows[0])
        same_count = sum(1 for r in rows if _row_normalized(r) == first_norm)
        first_cell = ""
        if rows and (isinstance(rows[0], (list, tuple)) and rows[0]) or rows[0] is not None:
            first_cell = str(rows[0][0] if isinstance(rows[0], (list, tuple)) else rows[0]).strip()
        page_num = sec.get("page")

        # Check PDF: if phrase appears many times on the page, don't treat as repetition
        if pdf_phrase_count is not None and page_num is not None and first_cell:
            try:
                count_in_pdf = pdf_phrase_count(int(page_num), first_cell)
                if count_in_pdf > REPEAT_PDF_COUNT_THRESHOLD:
                    log.debug("Section %s: phrase %r appears %d times on PDF page %s; skipping cleanup (treat as real data)",
                              sec.get("name"), first_cell[:30], count_in_pdf, page_num)
                    out.append(sec)
                    continue
            except Exception as e:
                log.debug("pdf_phrase_count failed for page %s: %s; using heuristic cleanup", page_num, e)

        # Collapse if all or nearly all rows are identical
        if same_count >= max(1, len(rows) * 9 // 10) and len(rows) > 1:
            rows = [rows[0]]
            sec["rows"] = rows
            sec["row_count"] = 1
        # Drop section if single row has all identical cells (model repetition)
        if len(rows) == 1:
            row = rows[0]
            cells = list(row) if isinstance(row, (list, tuple)) else [row]
            if len(cells) > 1:
                first_cell = str(cells[0]).strip() if cells else ""
                if first_cell and all(str(c).strip() == first_cell for c in cells):
                    log.debug("Dropping repetitive section %s (all cells identical: %s)", sec.get("name"), first_cell[:30])
                    continue
        # If headings are all the same repeated value (e.g. "Portfolio Number" x3), keep one
        if len(headings) > 1:
            h_norm = [str(h).strip() for h in headings]
            if h_norm and all(h == h_norm[0] for h in h_norm):
                sec["headings"] = [h_norm[0]]
        out.append(sec)
    return out


def _split_performance_sections(sections: list[dict]) -> list[dict]:
    """
    Post-process Performance sections so that:
    - The 4-column summary row (Beginning MV, Net Deposits, Investment Results, Ending MV)
      stays as its own section.
    - The strategy/benchmark percentage rows become a separate table with columns:
      Name, Current Month (%), Year to Date (%), Inception to Date (%).
    Handles both: (a) clean 4-column output from the model, (b) merged 6–8 column output
    where the model combined summary + percentage columns into one wide table.
    """
    out: list[dict] = []
    for sec in sections:
        name = (sec.get("name") or "").strip()
        rows = sec.get("rows") or []
        headings = sec.get("headings") or []
        col_count = sec.get("column_count", len(headings) or (len(rows[0]) if rows else 0))

        # Case 1: Model merged summary + percentage into one wide table (6–8 columns, 2+ rows)
        if (
            name.lower().startswith("performance")
            and 6 <= col_count <= 8
            and len(rows) >= 2
        ):
            # Summary: first row, first 4 columns
            summary_row = [c for c in rows[0][:4]]
            summary_headings = (headings[:4] if len(headings) >= 4 else
                ["Beginning Market Value", "Net Deposits (Withdrawals)", "Investment Results", "Ending Market Value"])
            summary_sec = dict(sec)
            summary_sec["headings"] = summary_headings
            summary_sec["rows"] = [summary_row]
            summary_sec["row_count"] = 1
            summary_sec["column_count"] = 4
            out.append(summary_sec)

            # Percent table: rows 1+, first column (name) + last 3 columns
            pct_headings = ["Name", "Current Month (%)", "Year to Date (%)", "Inception to Date (%)"]
            pct_rows: list[list[str]] = []
            for r in rows[1:]:
                if not r:
                    continue
                name_cell = r[0] if r else ""
                last_three = r[-3:] if len(r) >= 3 else [""] * 3
                pct_rows.append([name_cell] + last_three)
            if pct_rows:
                pct_sec = {
                    "name": f"{name} (%)",
                    "headings": pct_headings,
                    "rows": pct_rows,
                    "row_count": len(pct_rows),
                    "column_count": 4,
                }
                if "page" in sec:
                    pct_sec["page"] = sec["page"]
                out.append(pct_sec)
            continue

        # Case 2: Clean 4-column Performance (one summary row + percentage rows)
        if (
            name.lower().startswith("performance")
            and col_count == 4
            and len(rows) >= 2
        ):
            summary_row = rows[0]
            percent_rows = rows[1:]
            summary_sec = dict(sec)
            summary_sec["rows"] = [summary_row]
            summary_sec["row_count"] = 1
            out.append(summary_sec)
            pct_headings = ["Name", "Current Month (%)", "Year to Date (%)", "Inception to Date (%)"]
            pct_rows = []
            for r in percent_rows:
                if not r:
                    continue
                row = list(r) + [""] * max(0, 4 - len(r))
                pct_rows.append(row[:4])
            if pct_rows:
                pct_sec = {
                    "name": f"{name} (%)",
                    "headings": pct_headings,
                    "rows": pct_rows,
                    "row_count": len(pct_rows),
                    "column_count": 4,
                }
                if "page" in sec:
                    pct_sec["page"] = sec["page"]
                out.append(pct_sec)
            continue

        out.append(sec)
    return out


def _clear_duplicate_data_in_consecutive_rows(sections: list[dict]) -> list[dict]:
    """
    When two consecutive data rows have identical values in all columns except the first,
    and different labels in the first column, clear the first row's data (cols 1..N).
    This fixes model errors where blank rows get filled by copying the next row (e.g.
    Municipal Bond row with blank cells filled from MSCI row). Universal heuristic.
    """
    for sec in sections:
        rows = sec.get("rows") or []
        if len(rows) < 2:
            continue
        nc = sec.get("column_count", len(rows[0]) if rows else 0)
        if nc < 2:
            continue
        changed = False
        for i in range(len(rows) - 1):
            r0, r1 = rows[i], rows[i + 1]
            if len(r0) < nc or len(r1) < nc:
                continue
            label0 = str(r0[0]).strip()
            label1 = str(r1[0]).strip()
            if label0 == label1:
                continue
            data0 = [str(c).strip() for c in r0[1:nc]]
            data1 = [str(c).strip() for c in r1[1:nc]]
            if data0 and data0 == data1:
                # First row's data is a copy of next row; clear it
                rows[i] = [r0[0]] + [""] * (nc - 1)
                changed = True
        if changed:
            sec["rows"] = rows
    return sections


def _normalize_sections(sections: list[dict]) -> list[dict]:
    """Ensure each section's rows have exactly column_count cells (pad or trim)."""
    for sec in sections:
        nc = sec.get("column_count", 0)
        rows = sec.get("rows") or []
        if nc <= 0 and rows:
            nc = len(rows[0]) if rows else 0
            sec["column_count"] = nc
        if nc and rows:
            normalized = []
            for row in rows:
                if len(row) > nc:
                    normalized.append(row[:nc])
                elif len(row) < nc:
                    normalized.append(row + [""] * (nc - len(row)))
                else:
                    normalized.append(row)
            sec["rows"] = normalized
            sec["row_count"] = len(normalized)
    return sections


def pdf_to_json_vl(
    pdf_path: str | Path,
    output_path: str | Path,
    prompt: str | None = None,
    schema_type: str | None = None,
    max_pages: int | None = 10,
    page_ranges: list[int] | None = None,
    max_tokens: int | None = None,
    image_scale: float | None = None,
    max_vl_pages_per_run: int | None = None,
    llm=None,
) -> str:
    """
    Extract PDF with VL and write the project's canonical JSON format.
    Same schema as pdf_to_json (sections with name, headings, rows) so you can
    run: python run.py from-json <output.json> -o out.xlsx
    If schema_type is set (universal, generic, broker_statement, tax_statement), uses that prompt profile.
    If schema_type is None, document type is auto-detected from PDF text (no user selection); then the matching prompt is used.
    """
    detected_type = None
    if prompt is None:
        if schema_type is not None:
            prompt = _get_prompt_for_schema(schema_type)
        else:
            detected_type = detect_document_type(pdf_path)
            prompt = _get_prompt_for_schema(detected_type)
    text, meta = extract_pdf_with_vl(
        pdf_path,
        prompt=prompt,
        max_pages=max_pages,
        llm=llm,
        page_ranges=page_ranges,
        image_scale=image_scale,
        max_tokens=max_tokens,
        max_vl_pages_per_run=max_vl_pages_per_run,
    )
    sections = _vl_text_to_sections(text)
    sections = _normalize_sections(sections)
    sections = _drop_repetitive_sections(sections)
    sections = _split_performance_sections(sections)
    sections = _clear_duplicate_data_in_consecutive_rows(sections)
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    meta_out = {
        "pdf_name": Path(pdf_path).name,
        "pdf_path": str(Path(pdf_path).resolve()),
        "pages_processed": meta.get("page_numbers", []),
        "vl_timing_seconds": meta.get("total_seconds"),
        "vl_per_page_seconds": meta.get("per_page_seconds", []),
    }
    if detected_type is not None:
        meta_out["detected_document_type"] = detected_type
    payload = {
        "sections": sections,
        "meta": meta_out,
    }
    with open(out, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    log.info("Wrote %d section(s) to %s", len(sections), out)
    return str(out)


def main():
    """CLI: python -m extract_vl <pdf_path> [--json FILE] [--out FILE] [--max-pages N] [--page-ranges 1-5,10] [--schema-type TYPE]"""
    import argparse
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    parser = argparse.ArgumentParser(description="Extract content from PDF using Qwen2.5-VL (vision)")
    parser.add_argument("pdf_path", type=Path, help="Path to PDF")
    parser.add_argument("--prompt", default=None, help="Override prompt (default: from --schema-type or table extraction)")
    parser.add_argument("--schema-type", default=None, choices=list(PROMPT_PROFILES), help="Prompt profile: universal (any PDF), generic, broker_statement, tax_statement")
    parser.add_argument("--max-pages", type=int, default=10, help="Max pages to process (default 10)")
    parser.add_argument("--page-ranges", type=str, default=None, help="Only process these pages, e.g. 1-5,10-20")
    parser.add_argument("--max-tokens", type=int, default=None, help="Max tokens per page (default from config)")
    parser.add_argument("--image-scale", type=float, default=None, help="Render scale 2.0=fast, 3.0=clearer (default from config)")
    parser.add_argument("--out", type=Path, default=None, help="Write raw text to file (default: stdout)")
    parser.add_argument("--json", type=Path, default=None, dest="json_path", help="Write canonical JSON (sections + meta) to FILE")
    args = parser.parse_args()

    if not args.pdf_path.exists():
        print(f"Error: not found: {args.pdf_path}", file=sys.stderr)
        sys.exit(1)

    page_ranges = _parse_page_ranges(args.page_ranges) if args.page_ranges else None

    if args.json_path:
        result = pdf_to_json_vl(
            args.pdf_path,
            args.json_path,
            prompt=args.prompt,
            schema_type=args.schema_type,
            max_pages=args.max_pages,
            page_ranges=page_ranges,
            max_tokens=args.max_tokens,
            image_scale=args.image_scale,
        )
        print(f"JSON: {result}")
    else:
        text, _ = extract_pdf_with_vl(
            args.pdf_path,
            prompt=args.prompt or _get_prompt_for_schema(args.schema_type or "generic"),
            max_pages=args.max_pages,
            page_ranges=page_ranges,
            max_tokens=args.max_tokens,
            image_scale=args.image_scale,
        )
        if args.out:
            args.out.write_text(text, encoding="utf-8")
            print(f"Wrote {args.out}")
        else:
            print(text)


if __name__ == "__main__":
    main()
