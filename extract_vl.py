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
        raise ImportError("Install VL dependencies: pip install -r requirements-vl.txt") from e

    model_path, mmproj_path = _model_paths()
    if not model_path.exists():
        raise FileNotFoundError(f"Model not found: {model_path}. Run: python scripts/download_qwen2vl.py")
    if not mmproj_path.exists():
        raise FileNotFoundError(f"Mmproj not found: {mmproj_path}. Run: python scripts/download_qwen2vl.py")

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
    "us tax summary",
    "tax summary",
    "reportable income",
    "dividends and distributions",
    "qualified us dividends",
    "non-qualified us dividends",
    "reportable interest",
    "non-reportable items",
    "accrued interest paid at purchase",
    "form 1099",
    "1099-",
]
DOC_TYPE_BROKER_PHRASES = [
    "portfolio information",
    "portfolio activity",
    "statement of net assets",
    "statement of operations",
    "holdings",
    "investment results",
    "account statement",
    "broker",
    "market value as of",
    "change in market value",
    "asset allocation",
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
            indices = [p - 1 for p in page_ranges if 1 <= p <= total_pages]
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
