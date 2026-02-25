#!/usr/bin/env python3
"""
Web UI for PDF → Excel.

Run: flask --app app run
Or:  python app.py

Then open http://127.0.0.1:5000 — upload a PDF, choose "All tables" or "Ask AI" with a query, get Excel.
"""

import os
import tempfile
from pathlib import Path

from flask import Flask, render_template, request, send_file, flash, redirect, url_for
from werkzeug.exceptions import RequestEntityTooLarge

# Import after we're in the app directory
from tables_to_excel import pdf_tables_to_excel
from extract import extract_pdf_to_excel as extract_pdf_to_excel_anthropic
from extract_gemini import extract_pdf_to_excel as extract_pdf_to_excel_gemini

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-change-in-production")

# Max upload: 32 MB for AI path; allow slightly more for tables-only (we'll check in extract)
APP_ROOT = Path(__file__).resolve().parent
MAX_CONTENT_LENGTH = 40 * 1024 * 1024  # 40 MB
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH


def _get_upload_limit_mb():
    return MAX_CONTENT_LENGTH // (1024 * 1024)


@app.errorhandler(RequestEntityTooLarge)
def too_large(e):
    flash(f"File too large. Maximum size is {_get_upload_limit_mb()} MB.")
    return redirect(url_for("index"))


@app.route("/")
def index():
    return render_template("index.html", max_mb=_get_upload_limit_mb())


@app.route("/extract", methods=["POST"])
def extract():
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

    mode = request.form.get("mode", "tables")
    query = (request.form.get("query") or "").strip()

    if mode == "ask" and not query:
        flash("For “Ask AI”, please enter what you want to extract (e.g. “company taxes for January 2026”).")
        return redirect(url_for("index"))

    tmp_dir = None
    try:
        tmp_dir = tempfile.mkdtemp()
        pdf_path = Path(tmp_dir) / "upload.pdf"
        file.save(str(pdf_path))

        out_path = Path(tmp_dir) / "output.xlsx"

        if mode == "tables":
            result = pdf_tables_to_excel(str(pdf_path), str(out_path), overwrite=True)
        else:
            # Prefer Gemini (free tier) if key is set; otherwise Anthropic
            if os.environ.get("GEMINI_API_KEY"):
                result = extract_pdf_to_excel_gemini(str(pdf_path), query, str(out_path))
            elif os.environ.get("ANTHROPIC_API_KEY"):
                result = extract_pdf_to_excel_anthropic(str(pdf_path), query, str(out_path))
            else:
                flash("For “Ask AI”, set GEMINI_API_KEY (free at aistudio.google.com) or ANTHROPIC_API_KEY in .env.")
                return redirect(url_for("index"))

        if not Path(result).exists():
            flash("Conversion produced no file.")
            return redirect(url_for("index"))

        base_name = Path(file.filename).stem
        download_name = f"{base_name}.xlsx"
        return send_file(
            result,
            as_attachment=True,
            download_name=download_name,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    except FileNotFoundError as e:
        flash(str(e))
        return redirect(url_for("index"))
    except ValueError as e:
        flash(str(e))
        return redirect(url_for("index"))
    except Exception as e:
        msg = str(e).lower()
        if "401" in msg or "auth" in msg or "api key" in msg or "invalid" in msg:
            flash("Invalid or missing API key. Set GEMINI_API_KEY (free) or ANTHROPIC_API_KEY in .env for “Ask AI”.")
        elif "429" in msg or "rate" in msg:
            flash("API rate limit exceeded. Try again later.")
        else:
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
