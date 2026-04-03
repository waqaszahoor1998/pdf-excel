"""Smoke test for scripts/evaluate_public_pdfs.py on the tiny committed fixture only."""

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "evaluation" / "public_pdfs" / "generated_sample_report.pdf"


def _load_eval_module():
    path = ROOT / "scripts" / "evaluate_public_pdfs.py"
    spec = importlib.util.spec_from_file_location("evaluate_public_pdfs", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.skipif(not SAMPLE.exists(), reason="evaluation/public_pdfs/generated_sample_report.pdf missing")
def test_evaluate_script_runs_on_sample():
    mod = _load_eval_module()
    meta = mod._corpus_by_filename().get(SAMPLE.name)
    out = mod._eval_one(SAMPLE, meta)
    assert "error" not in out
    assert out.get("sections", 0) >= 1
    assert out.get("qc_status") == "ok"
