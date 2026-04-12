#!/usr/bin/env python3
"""
Web UI for PDF → Excel (local only, no cloud LLM).

Run: flask --app app run
Or:  python app.py

Then open http://127.0.0.1:8003 — upload a PDF, get all tables as Excel.
Default port is **8003** (see `.flaskenv` / `FLASK_RUN_PORT`; override with `--port`).
Extraction: default uses pdfplumber + QB shaping. Choose hybrid (library + VL on
difficult pages) or vision-only for scans; optional Ask AI uses Anthropic. After
extraction, the first pages are audited vs the PDF; summary is in JSON meta and
the ZIP may include a full audit report. The home page also has **Family QB template**:
upload empty family_template.xlsx plus optional JPM / Goldman PDFs → one filled workbook
(POST `/populate-family-template`). No raw data is sent to any cloud service except
Ask AI when that mode is used.
"""

import io
import json
import logging
import os
import tempfile
import zipfile
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, render_template, request, send_file, flash, redirect, url_for
from werkzeug.exceptions import RequestEntityTooLarge

_env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(_env_path)
# Set CUDA before any VL/llama_cpp use so GPU is used
try:
    from extract_vl import _ensure_cuda_path
    _ensure_cuda_path()
except ImportError:
    pass
log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s [%(name)s] %(message)s")

from tables_to_excel import (
    extract_sections_from_pdf,
    _write_json_from_sections,
    load_sections_from_json,
    _write_sections_to_workbook,
    write_sections_to_workbook_by_page,
    _normalize_page_to_sheet,
)
from pdf_to_qb import pdf_to_qb_excel, transform_extracted_to_qb
from pdf_json_audit import apply_audit_to_extraction_file

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-change-in-production")

# Max upload size for PDFs (from env or default)
APP_ROOT = Path(__file__).resolve().parent
_val = (os.environ.get("MAX_UPLOAD_MB") or "").strip() or "40"
_default_mb = max(1, min(100, int(_val) if _val.isdigit() else 40))
MAX_CONTENT_LENGTH = _default_mb * 1024 * 1024
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH

# Web UI: cap VL/hybrid page count; audit runs on full PDF by default (see AUDIT_MAX_PAGES)
WEB_MAX_VL_PAGES = 20


def _web_audit_page_cap():
    """None = audit all pages. Set AUDIT_MAX_PAGES=N to audit first N only (faster)."""
    v = (os.environ.get("AUDIT_MAX_PAGES") or "").strip()
    if not v:
        return None
    try:
        n = int(v)
        return n if n > 0 else None
    except ValueError:
        return None


def _get_upload_limit_mb():
    return MAX_CONTENT_LENGTH // (1024 * 1024)


def _ai_available():
    return bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())


def _vl_available():
    """True if VL extraction (Qwen2.5-VL) is installed and model is present."""
    try:
        from extract_vl import _model_paths
        model_path, mmproj_path = _model_paths()
        return model_path and Path(model_path).exists() and mmproj_path and Path(mmproj_path).exists()
    except Exception:
        return False


def _extract_method_from_form(form) -> str:
    """library | hybrid | vl — default library."""
    m = (form.get("extract_method") or "").strip().lower()
    if m in ("library", "hybrid", "vl"):
        return m
    return "vl" if (form.get("use_vl") or "").strip().lower() in ("on", "1", "yes", "true") else "library"


def _flash_audit_summary(json_path: Path) -> None:
    """Flash a short message from meta.audit_summary after apply_audit_to_extraction_file."""
    try:
        payload = json.loads(json_path.read_text(encoding="utf-8"))
        meta = payload.get("meta") or {}
        aud = meta.get("audit_summary") or {}
        if int(aud.get("pages_audited") or 0) == 0:
            return
        conf = aud.get("confidence_pct")
        if aud.get("passed_automation"):
            flash(
                f"Audit: automation pass (confidence {conf}%, scope {aud.get('audit_scope', '?')}).",
                "success",
            )
        else:
            flash(
                (aud.get("automation_reason") or "Audit: automation failed.")
                + f" — confidence {conf}%.",
                "warning",
            )
    except Exception:
        pass


@app.errorhandler(RequestEntityTooLarge)
def too_large(e):
    flash(f"File too large. Maximum size is {_get_upload_limit_mb()} MB.")
    return redirect(url_for("index"))


@app.route("/")
def index():
    return render_template(
        "index.html",
        max_mb=_get_upload_limit_mb(),
        ai_available=_ai_available(),
        vl_available=_vl_available(),
    )


@app.route("/extract", methods=["POST"])
def extract():
    if "pdf" not in request.files:
        log.warning("extract: no file in request")
        flash("No file selected.")
        return redirect(url_for("index"))

    file = request.files["pdf"]
    if not file or file.filename == "":
        log.warning("extract: empty filename")
        flash("No file selected.")
        return redirect(url_for("index"))

    if not file.filename.lower().endswith(".pdf"):
        flash("Please upload a PDF file.")
        return redirect(url_for("index"))

    mode = (request.form.get("mode") or "offline").strip().lower()
    query = (request.form.get("query") or "").strip()
    if mode == "ai":
        if not query:
            flash("Enter a query for Ask AI (e.g. 'taxes for January').")
            return redirect(url_for("index"))
        if not _ai_available():
            flash("Ask AI requires ANTHROPIC_API_KEY in .env.")
            return redirect(url_for("index"))

    tmp_dir = None
    try:
        tmp_dir = tempfile.mkdtemp()
        pdf_path = Path(tmp_dir) / "upload.pdf"
        file.save(str(pdf_path))
        use_ai = mode == "ai" and query and _ai_available()
        log.info("extract: saved upload (mode=%s)", "ai" if use_ai else "offline")

        out_path = Path(tmp_dir) / "output.xlsx"
        json_path = Path(tmp_dir) / "output.json"
        audit_report_path = Path(tmp_dir) / "audit_report.json"
        extract_method = _extract_method_from_form(request.form)
        if use_ai:
            from config import load_config
            from extract import extract_pdf_to_excel
            cfg = load_config()
            result = extract_pdf_to_excel(str(pdf_path), query, str(out_path), config=cfg)
            json_path = None  # AI path does not produce JSON in same format
            audit_report_path = None
        elif extract_method in ("hybrid", "vl") and not _vl_available():
            flash(
                "Hybrid and vision-only extraction need the local vision model. "
                "Install requirements-vl.txt and run scripts/download_qwen2vl.py.",
            )
            return redirect(url_for("index"))
        elif extract_method == "hybrid":
            try:
                from hybrid_extract import hybrid_pdf_to_json

                hybrid_pdf_to_json(
                    str(pdf_path),
                    str(json_path),
                    max_pages=WEB_MAX_VL_PAGES,
                    overwrite=True,
                )
                sections = load_sections_from_json(json_path)
                with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
                    temp_xlsx = f.name
                try:
                    _write_sections_to_workbook(sections, Path(temp_xlsx))
                    transform_extracted_to_qb(temp_xlsx, str(out_path))
                finally:
                    Path(temp_xlsx).unlink(missing_ok=True)
                result = str(out_path)
            except ImportError:
                log.exception("Hybrid extract: import failed")
                flash("Hybrid extraction requires the vision stack (requirements-vl.txt).")
                return redirect(url_for("index"))
            except FileNotFoundError:
                log.exception("Hybrid extract: model or file not found")
                flash("Vision model files not found. Run scripts/download_qwen2vl.py to download the model.")
                return redirect(url_for("index"))
            except Exception as e:
                log.exception("Hybrid extract: %s", e)
                flash(f"Hybrid extraction failed: {e}")
                return redirect(url_for("index"))
        elif extract_method == "vl":
            # Vision model path: PDF → VL → JSON → Excel (for scanned PDFs)
            try:
                from extract_vl import pdf_to_json_vl

                pdf_to_json_vl(str(pdf_path), str(json_path), max_pages=WEB_MAX_VL_PAGES)
                sections = load_sections_from_json(json_path)
                with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
                    temp_xlsx = f.name
                try:
                    _write_sections_to_workbook(sections, Path(temp_xlsx))
                    transform_extracted_to_qb(temp_xlsx, str(out_path))
                finally:
                    Path(temp_xlsx).unlink(missing_ok=True)
                result = str(out_path)
            except ImportError:
                log.exception("VL extract: import failed")
                flash("Vision model not available. Install requirements-vl.txt and run scripts/download_qwen2vl.py.")
                return redirect(url_for("index"))
            except FileNotFoundError:
                log.exception("VL extract: model or file not found")
                flash("Vision model files not found. Run scripts/download_qwen2vl.py to download the model.")
                return redirect(url_for("index"))
            except Exception as e:
                log.exception("VL extract: %s", e)
                flash(f"Vision extraction failed: {e}")
                return redirect(url_for("index"))
        else:
            result = pdf_to_qb_excel(
                str(pdf_path), str(out_path), overwrite=True, json_path_out=str(json_path)
            )

        if json_path and json_path.exists() and not use_ai:
            apply_audit_to_extraction_file(
                pdf_path,
                json_path,
                audit_pages=_web_audit_page_cap(),
                report_path=audit_report_path,
                silent=True,
            )
            _flash_audit_summary(json_path)

        if not Path(result).exists():
            log.error("extract: result file missing %s", result)
            flash("Conversion produced no file.")
            return redirect(url_for("index"))

        base_name = Path(file.filename).stem
        if json_path and json_path.exists():
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
                zf.write(result, f"{base_name}.xlsx")
                zf.write(json_path, f"{base_name}.json")
                if audit_report_path and audit_report_path.exists():
                    zf.write(audit_report_path, f"{base_name}_audit_report.json")
            buf.seek(0)
            log.info("extract: sending zip with %s.xlsx and %s.json", base_name, base_name)
            return send_file(
                buf,
                as_attachment=True,
                download_name=f"{base_name}.zip",
                mimetype="application/zip",
            )
        download_name = f"{base_name}.xlsx"
        log.info("extract: sending file %s", download_name)
        return send_file(
            result,
            as_attachment=True,
            download_name=download_name,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    except FileNotFoundError as e:
        log.exception("extract: FileNotFoundError")
        flash(str(e))
        return redirect(url_for("index"))
    except ValueError as e:
        log.exception("extract: ValueError")
        flash(str(e))
        return redirect(url_for("index"))
    except Exception as e:
        log.exception("extract: %s", e)
        flash(f"Error: {e}")
        return redirect(url_for("index"))
    finally:
        if tmp_dir and Path(tmp_dir).exists():
            try:
                for f in Path(tmp_dir).iterdir():
                    f.unlink(missing_ok=True)
                Path(tmp_dir).rmdir()
            except OSError:
                pass


@app.route("/pdf-to-json", methods=["POST"])
def pdf_to_json_route():
    """Step 1: PDF → JSON only. Download JSON (meta includes audit summary on sampled pages)."""
    if "pdf" not in request.files:
        flash("No file selected.")
        return redirect(url_for("index"))
    file = request.files["pdf"]
    if not file or file.filename == "":
        flash("No file selected.")
        return redirect(url_for("index"))
    if not file.filename.lower().endswith(".pdf"):
        flash("Please upload a PDF file.")
        return redirect(url_for("index"))
    extract_method = _extract_method_from_form(request.form)
    if extract_method in ("hybrid", "vl") and not _vl_available():
        flash(
            "Hybrid and vision-only need the local vision model. "
            "Install requirements-vl.txt and run scripts/download_qwen2vl.py.",
        )
        return redirect(url_for("index"))
    tmp_dir = None
    try:
        tmp_dir = tempfile.mkdtemp()
        pdf_path = Path(tmp_dir) / "upload.pdf"
        file.save(str(pdf_path))
        json_path = Path(tmp_dir) / "output.json"
        audit_report_path = Path(tmp_dir) / "audit_report.json"
        if extract_method == "hybrid":
            from hybrid_extract import hybrid_pdf_to_json

            hybrid_pdf_to_json(
                str(pdf_path),
                str(json_path),
                max_pages=WEB_MAX_VL_PAGES,
                overwrite=True,
            )
        elif extract_method == "vl":
            from extract_vl import pdf_to_json_vl

            pdf_to_json_vl(str(pdf_path), str(json_path), max_pages=WEB_MAX_VL_PAGES)
        else:
            sections = extract_sections_from_pdf(str(pdf_path))
            _write_json_from_sections(sections, json_path, overwrite=True)
        if not json_path.exists():
            flash("Conversion produced no JSON.")
            return redirect(url_for("index"))
        apply_audit_to_extraction_file(
            pdf_path,
            json_path,
            audit_pages=_web_audit_page_cap(),
            report_path=audit_report_path,
            silent=True,
        )
        _flash_audit_summary(json_path)
        base_name = Path(file.filename).stem
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(json_path, f"{base_name}.json")
            if audit_report_path.exists():
                zf.write(audit_report_path, f"{base_name}_audit_report.json")
        buf.seek(0)
        return send_file(
            buf,
            as_attachment=True,
            download_name=f"{base_name}_json.zip",
            mimetype="application/zip",
        )
    except Exception as e:
        log.exception("pdf-to-json: %s", e)
        flash(f"Error: {e}")
        return redirect(url_for("index"))
    finally:
        if tmp_dir and Path(tmp_dir).exists():
            try:
                for f in Path(tmp_dir).iterdir():
                    f.unlink(missing_ok=True)
                Path(tmp_dir).rmdir()
            except OSError:
                pass


@app.route("/json-to-excel", methods=["POST"])
def json_to_excel_route():
    """Step 2: JSON → Excel. Upload JSON (from PDF→JSON or edited) to get structured xlsx.
    If JSON meta or config has page_to_sheet, sections are grouped by page into sheets.
    """
    import json as _json
    if "json_file" not in request.files:
        flash("No file selected.")
        return redirect(url_for("index"))
    file = request.files["json_file"]
    if not file or file.filename == "":
        flash("No file selected.")
        return redirect(url_for("index"))
    if not file.filename.lower().endswith(".json"):
        flash("Please upload a JSON file (from PDF→JSON step).")
        return redirect(url_for("index"))
    tmp_dir = None
    try:
        tmp_dir = tempfile.mkdtemp()
        json_path = Path(tmp_dir) / "input.json"
        file.save(str(json_path))
        out_xlsx = Path(tmp_dir) / "output.xlsx"
        sections = load_sections_from_json(json_path)
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
            write_sections_to_workbook_by_page(sections, page_to_sheet, out_xlsx)
        else:
            with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
                temp_xlsx = f.name
            try:
                _write_sections_to_workbook(sections, Path(temp_xlsx))
                transform_extracted_to_qb(temp_xlsx, str(out_xlsx))
            finally:
                Path(temp_xlsx).unlink(missing_ok=True)
        if not out_xlsx.exists():
            flash("Conversion produced no Excel file.")
            return redirect(url_for("index"))
        base_name = Path(file.filename).stem
        download_name = f"{base_name}.xlsx"
        return send_file(
            str(out_xlsx),
            as_attachment=True,
            download_name=download_name,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    except Exception as e:
        log.exception("json-to-excel: %s", e)
        flash(f"Error: {e}")
        return redirect(url_for("index"))
    finally:
        if tmp_dir and Path(tmp_dir).exists():
            try:
                for f in Path(tmp_dir).iterdir():
                    f.unlink(missing_ok=True)
                Path(tmp_dir).rmdir()
            except OSError:
                pass


def _parse_gs_account_list(gs_account_raw: str, n_pdfs: int) -> tuple[list[str | None] | None, str | None]:
    """
    Same rules as CLI --gs-account: one value for all, or comma list matching PDF count.
    Returns (accounts, error_message).
    """
    raw = (gs_account_raw or "").strip()
    if not raw:
        return [None] * n_pdfs, None
    parts = [x.strip() for x in raw.split(",") if x.strip()]
    if len(parts) == n_pdfs:
        return parts, None
    if len(parts) == 1:
        return [parts[0]] * n_pdfs, None
    return (
        None,
        "Goldman account IDs: enter one value for all PDFs, or a comma-separated list with the same count as Goldman PDFs.",
    )


@app.route("/populate-family-template", methods=["POST"])
def populate_family_template_route():
    """
    Upload empty family template (.xlsx) plus optional JPM PDF and/or one or more Goldman PDFs.
    Returns one filled workbook (JPM blocks from PDF text; Goldman via PDF→QB→template).
    """
    from scripts.family_template_merge import populate_family_template

    if "template" not in request.files:
        flash("Choose your empty family template Excel file.", "error")
        return redirect(url_for("index"))

    tpl_file = request.files["template"]
    if not tpl_file or not tpl_file.filename:
        flash("Choose your empty family template Excel file.", "error")
        return redirect(url_for("index"))

    fn = tpl_file.filename.lower()
    if not (fn.endswith(".xlsx") or fn.endswith(".xlsm")):
        flash("Template must be .xlsx or .xlsm.", "error")
        return redirect(url_for("index"))

    jpm_upload = request.files.get("jpm_pdf")
    jpm_ok = bool(
        jpm_upload
        and jpm_upload.filename
        and jpm_upload.filename.lower().endswith(".pdf")
    )
    gs_uploads = [
        f
        for f in request.files.getlist("gs_pdfs")
        if f and f.filename and f.filename.lower().endswith(".pdf")
    ]

    if not jpm_ok and not gs_uploads:
        flash("Add at least one PDF: JP Morgan and/or Goldman (hold Ctrl/Cmd to select multiple Goldman files).", "error")
        return redirect(url_for("index"))

    gs_account_raw = (request.form.get("gs_account") or "").strip()
    if gs_uploads:
        accts, acct_err = _parse_gs_account_list(gs_account_raw, len(gs_uploads))
        if acct_err:
            flash(acct_err, "error")
            return redirect(url_for("index"))
    else:
        accts = []

    jpm_accounts = None
    jpm_accounts_raw = (request.form.get("jpm_accounts") or "").strip()
    if jpm_accounts_raw:
        jpm_accounts = [x.strip() for x in jpm_accounts_raw.split(",") if x.strip()]

    tmp_dir = None
    try:
        tmp_dir = tempfile.mkdtemp()
        tdir = Path(tmp_dir)
        tpl_path = tdir / "template.xlsx"
        tpl_file.save(str(tpl_path))

        jpm_path = None
        if jpm_ok:
            jpm_path = tdir / "jpm.pdf"
            jpm_upload.save(str(jpm_path))

        pairs: list[tuple[str, str | None]] = []
        for i, g in enumerate(gs_uploads):
            gp = tdir / f"gs_{i}.pdf"
            g.save(str(gp))
            pairs.append((str(gp), accts[i]))

        out_path = tdir / "family_template_filled.xlsx"
        log.info(
            "populate-family-template: jpm=%s gs_count=%s",
            bool(jpm_path),
            len(pairs),
        )
        populate_family_template(
            tpl_path,
            out_path,
            jpm_pdf=str(jpm_path) if jpm_path else None,
            jpm_accounts=jpm_accounts,
            gs_pdf_account_pairs=pairs or None,
        )

        if not out_path.exists():
            flash("Template fill produced no file.", "error")
            return redirect(url_for("index"))

        buf = io.BytesIO(out_path.read_bytes())
        buf.seek(0)
        download = "family_template_filled.xlsx"
        return send_file(
            buf,
            as_attachment=True,
            download_name=download,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    except Exception as e:
        log.exception("populate-family-template: %s", e)
        flash(f"Template fill failed: {e}", "error")
        return redirect(url_for("index"))
    finally:
        if tmp_dir and Path(tmp_dir).exists():
            try:
                for f in Path(tmp_dir).iterdir():
                    f.unlink(missing_ok=True)
                Path(tmp_dir).rmdir()
            except OSError:
                pass


if __name__ == "__main__":
    _port = int(os.environ.get("FLASK_RUN_PORT", "8003"))
    _host = os.environ.get("FLASK_RUN_HOST", "127.0.0.1")
    app.run(debug=True, host=_host, port=_port)
