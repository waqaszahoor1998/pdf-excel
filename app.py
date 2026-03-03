#!/usr/bin/env python3
"""
Web UI for PDF → Excel (local only, no cloud LLM).

Run: flask --app app run
Or:  python app.py

Then open http://127.0.0.1:5000 — upload a PDF, get all tables as Excel.
Extraction uses pdfplumber only; no raw data is sent to any cloud service.
"""

import logging
import os
import tempfile
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, render_template, request, send_file, flash, redirect, url_for
from werkzeug.exceptions import RequestEntityTooLarge

_env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(_env_path)
log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s [%(name)s] %(message)s")

from tables_to_excel import pdf_tables_to_excel
from pdf_to_qb import pdf_to_qb_excel

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-change-in-production")

# Max upload size for PDFs (from env or default)
APP_ROOT = Path(__file__).resolve().parent
_val = (os.environ.get("MAX_UPLOAD_MB") or "").strip() or "40"
_default_mb = max(1, min(100, int(_val) if _val.isdigit() else 40))
MAX_CONTENT_LENGTH = _default_mb * 1024 * 1024
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH


def _get_upload_limit_mb():
    return MAX_CONTENT_LENGTH // (1024 * 1024)


def _ai_available():
    return bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())


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
        if use_ai:
            from config import load_config
            from extract import extract_pdf_to_excel
            cfg = load_config()
            result = extract_pdf_to_excel(str(pdf_path), query, str(out_path), config=cfg)
        else:
            result = pdf_to_qb_excel(str(pdf_path), str(out_path), overwrite=True)

        if not Path(result).exists():
            log.error("extract: result file missing %s", result)
            flash("Conversion produced no file.")
            return redirect(url_for("index"))

        base_name = Path(file.filename).stem
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


if __name__ == "__main__":
    app.run(debug=True, port=5000)
