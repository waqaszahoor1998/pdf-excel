#!/usr/bin/env python3
"""
Single entry point for PDF → Excel.

  python run.py tables <pdf> [pdf2 ...]   Extract all tables to QB-format Excel. Batch: multiple PDFs → multiple .xlsx.
  python run.py json <pdf> [pdf2 ...]     Extract PDF to JSON first (sections + rows); then you can convert to Excel.
  python run.py ask <pdf> <query>         AI agent: extract what you ask for. Optional: multiple PDFs with same query.
"""

import argparse
import sys
from pathlib import Path


def _get_version():
    p = Path(__file__).resolve().parent / "VERSION"
    return p.read_text().strip() if p.exists() else "0.0.0"


# Set CUDA before any VL/llama_cpp use so GPU is used
try:
    from extract_vl import _ensure_cuda_path

    _ensure_cuda_path()
except ImportError:
    pass

# Project modules
from tables_to_excel import pdf_tables_to_excel, pdf_to_json, json_to_excel
from extract import extract_pdf_to_excel
from pdf_to_qb import pdf_to_qb_excel, transform_extracted_to_qb


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


def _default_output_dir():
    """Default output directory (e.g. output/). Can be overridden via OUTPUT_DIR in .env."""
    try:
        from dotenv import load_dotenv
        import os
        load_dotenv()
        return os.environ.get("OUTPUT_DIR", "output")
    except Exception:
        return "output"


def cmd_tables(args) -> int:
    overwrite = not args.no_overwrite
    pdfs = _expand_pdfs(args.pdfs)
    if not pdfs:
        print("Error: No PDF files found.", file=sys.stderr)
        return 1
    if args.output and len(pdfs) > 1:
        print("Error: -o/--output only allowed for a single PDF.", file=sys.stderr)
        return 1
    default_dir = _default_output_dir()
    for i, pdf in enumerate(pdfs):
        if args.output and len(pdfs) == 1:
            out = args.output
        else:
            out = str(Path(default_dir) / Path(pdf).with_suffix(".xlsx").name)
        if len(pdfs) > 1:
            print(f"[{i+1}/{len(pdfs)}] {pdf}")
        try:
            out_path = Path(out)
            result = pdf_to_qb_excel(
                str(pdf),
                out,
                overwrite=overwrite,
                json_path_out=str(out_path.with_suffix(".json")),
            )
            print(f"Saved: {result}")
            if out_path.with_suffix(".json").exists():
                print(f"Saved: {out_path.with_suffix('.json')}")
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
    return 0


def cmd_clean_json(args) -> int:
    """Remove repetitive sections from extraction JSON. When --pdf is given, only collapse/drop when the repeated phrase appears few times on that PDF page (compare with source). Overwrites the file."""
    import json as _json
    from extract_vl import _drop_repetitive_sections, pdf_phrase_count_for_file

    json_path = Path(args.json_file)
    if not json_path.exists():
        print(f"Error: File not found: {json_path}", file=sys.stderr)
        return 1
    with open(json_path, encoding="utf-8") as f:
        payload = _json.load(f)
    sections = payload.get("sections") or []
    if not sections:
        print("No sections to clean.", file=sys.stderr)
        return 0
    pdf_path = getattr(args, "pdf", None)
    if not pdf_path:
        meta = payload.get("meta") or {}
        if meta.get("pdf_path") and Path(meta["pdf_path"]).exists():
            pdf_path = meta["pdf_path"]
        elif meta.get("pdf_name"):
            candidate = json_path.parent / meta["pdf_name"]
            if candidate.exists():
                pdf_path = candidate
    pdf_phrase_count = None
    if pdf_path and Path(pdf_path).exists():
        pdf_phrase_count = pdf_phrase_count_for_file(pdf_path)
        if pdf_phrase_count:
            print(f"Using PDF for comparison: {pdf_path}")
    before = len(sections)
    sections = _drop_repetitive_sections(sections, pdf_phrase_count=pdf_phrase_count)
    after = len(sections)
    payload["sections"] = sections
    with open(json_path, "w", encoding="utf-8") as f:
        _json.dump(payload, f, indent=2, ensure_ascii=False)
    print(f"Cleaned: {before} -> {after} sections (removed {before - after} repetitive). Saved: {json_path}")
    return 0


def cmd_from_json(args) -> int:
    """Convert a JSON file (from pdf→json) to Excel. Use after editing JSON to map tables correctly.
    If the JSON has meta.page_to_sheet or config has page_to_sheet, sections are grouped by page
    into sheets (e.g. page 2 → General Information, page 3 → Overview, pages 4–5 → US Tax Summary).
    """
    json_path = Path(args.json_file)
    if not json_path.exists():
        print(f"Error: File not found: {json_path}", file=sys.stderr)
        return 1
    if json_path.suffix.lower() != ".json":
        print("Error: File must be a .json file.", file=sys.stderr)
        return 1
    out = args.output or str(json_path.with_suffix(".xlsx"))
    out_path = Path(out)
    overwrite = not getattr(args, "no_overwrite", False)
    if out_path.exists() and not overwrite:
        print(f"Error: Output exists: {out_path} (use --overwrite to replace)", file=sys.stderr)
        return 1
    try:
        import json as _json
        import tempfile
        from tables_to_excel import (
            load_sections_from_json,
            _write_sections_to_workbook,
            write_sections_to_workbook_by_page,
            _normalize_page_to_sheet,
        )

        sections = load_sections_from_json(json_path)
        # Prefer page_to_sheet from JSON meta, then from config/vl.json
        page_to_sheet = {}
        with open(json_path, encoding="utf-8") as f:
            payload = _json.load(f)
        meta = payload.get("meta") or {}
        page_to_sheet = _normalize_page_to_sheet(meta.get("page_to_sheet") or {})
        if not page_to_sheet:
            vl_config_path = Path(__file__).resolve().parent / "config" / "vl.json"
            if vl_config_path.exists():
                with open(vl_config_path, encoding="utf-8") as f:
                    vl_cfg = _json.load(f)
                page_to_sheet = _normalize_page_to_sheet(vl_cfg.get("page_to_sheet") or {})
        has_page = any(len(s) >= 4 and s[3] is not None for s in sections)
        if page_to_sheet and has_page:
            write_sections_to_workbook_by_page(sections, page_to_sheet, out_path)
        else:
            with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
                temp_xlsx = f.name
            try:
                _write_sections_to_workbook(sections, Path(temp_xlsx))
                transform_extracted_to_qb(temp_xlsx, str(out_path))
            finally:
                Path(temp_xlsx).unlink(missing_ok=True)
        print(f"Saved: {out_path}")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    return 0


def cmd_json(args) -> int:
    pdfs = _expand_pdfs(args.pdfs)
    if not pdfs:
        print("Error: No PDF files found.", file=sys.stderr)
        return 1
    if args.output and len(pdfs) > 1:
        print("Error: -o/--output only allowed for a single PDF.", file=sys.stderr)
        return 1
    default_dir = _default_output_dir()
    for i, pdf in enumerate(pdfs):
        out = args.output if (args.output and len(pdfs) == 1) else str(Path(default_dir) / Path(pdf).with_suffix(".json").name)
        if len(pdfs) > 1:
            print(f"[{i+1}/{len(pdfs)}] {pdf}")
        try:
            result = pdf_to_json(str(pdf), out, overwrite=not args.no_overwrite)
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
    default_dir = _default_output_dir()
    for i, pdf in enumerate(pdfs):
        if args.output and len(pdfs) == 1:
            out = args.output
        else:
            out = str(Path(default_dir) / Path(pdf).with_suffix(".xlsx").name)
        if len(pdfs) > 1:
            print(f"[{i+1}/{len(pdfs)}] {pdf}")
        try:
            backend = getattr(args, "backend", "anthropic")
            if backend == "smollm":
                from extract_smollm import extract_pdf_to_excel as smollm_extract
                result = smollm_extract(str(pdf), args.query, out, model_name=getattr(args, "smollm_model", "HuggingFaceTB/SmolLM2-360M-Instruct"))
            else:
                from config import load_config
                cfg = load_config()
                result = extract_pdf_to_excel(str(pdf), args.query, out, model=args.model, config=cfg)
            print(f"Saved: {result}")
        except Exception as e:
            msg = str(e).lower()
            if "401" in msg or "auth" in msg or "invalid_api_key" in msg:
                print("Error: Invalid or missing API key. Set ANTHROPIC_API_KEY in .env.", file=sys.stderr)
            elif "429" in msg or "rate" in msg:
                print("Error: API rate limit exceeded. Try again later.", file=sys.stderr)
            else:
                print(f"Error: {e}", file=sys.stderr)
            return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="PDF → Excel: extract tables (offline) or ask the AI agent for specific data.",
        epilog="Examples:\n  %(prog)s tables report.pdf\n  %(prog)s tables a.pdf b.pdf\n  %(prog)s ask report.pdf \"taxes for January 2026\"",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=_get_version())
    sub = parser.add_subparsers(dest="cmd", required=True, help="Command")

    # tables: one or more PDFs
    p_tables = sub.add_parser("tables", help="Extract all tables from PDF(s) to Excel (no AI)")
    p_tables.add_argument("pdfs", nargs="+", help="PDF file(s) or directory containing PDFs")
    p_tables.add_argument("-o", "--output", default=None, help="Output .xlsx path (single PDF only)")
    p_tables.add_argument("--no-overwrite", action="store_true", help="Do not overwrite existing output")
    p_tables.set_defaults(func=cmd_tables)

    p_json = sub.add_parser("json", help="Extract PDF to JSON (sections + rows); easy to edit, then convert to Excel")
    p_json.add_argument("pdfs", nargs="+", help="PDF file(s) or directory containing PDFs")
    p_json.add_argument("-o", "--output", default=None, help="Output .json path (single PDF only)")
    p_json.add_argument("--no-overwrite", action="store_true", help="Do not overwrite existing output")
    p_json.set_defaults(func=cmd_json)

    p_from_json = sub.add_parser("from-json", help="Convert JSON (from pdf→json) to Excel; use after editing JSON to map tables")
    p_from_json.add_argument("json_file", help="Path to .json file (extraction output)")
    p_from_json.add_argument("-o", "--output", default=None, help="Output .xlsx path")
    p_from_json.add_argument("--no-overwrite", action="store_true", help="Do not overwrite existing output")
    p_from_json.set_defaults(func=cmd_from_json)

    p_clean_json = sub.add_parser("clean-json", help="Remove repetitive sections from extraction JSON; with --pdf, only clean when PDF confirms phrase is rare on that page")
    p_clean_json.add_argument("json_file", help="Path to .json file (extraction output)")
    p_clean_json.add_argument("--pdf", default=None, help="Path to source PDF; if set, we only collapse/drop when the repeated phrase appears ≤10 times on that page")
    p_clean_json.set_defaults(func=cmd_clean_json)

    # ask: PDF(s) + query
    p_ask = sub.add_parser("ask", help="AI agent: extract what you ask for from PDF(s)")
    p_ask.add_argument("pdf", nargs="+", help="PDF file(s) or directory containing PDFs")
    p_ask.add_argument("query", help="What to extract, e.g. 'company taxes for January 2026'")
    p_ask.add_argument("-o", "--output", default=None, help="Output .xlsx path (single PDF only)")
    p_ask.add_argument("--backend", choices=("anthropic", "smollm"), default="anthropic", help="AI backend: anthropic (API) or smollm (offline local)")
    p_ask.add_argument("--model", default="claude-sonnet-4-20250514", help="Anthropic model (when backend=anthropic)")
    p_ask.add_argument("--smollm-model", default="HuggingFaceTB/SmolLM2-360M-Instruct", help="HuggingFace model name (when backend=smollm)")
    p_ask.set_defaults(func=cmd_ask)

    args = parser.parse_args()
    try:
        return args.func(args)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
