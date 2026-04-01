#!/usr/bin/env python3
import json
import subprocess
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PY = ROOT / "venv" / "Scripts" / "python.exe"
RUN = ROOT / "run.py"
OUT_DIR = ROOT / "output" / "baseline"
REPORT = ROOT / "docs" / "BASELINE_PROFILE.md"


def _run(cmd: list[str]) -> float:
    t0 = time.perf_counter()
    subprocess.run(cmd, cwd=ROOT, check=True)
    return time.perf_counter() - t0


def _read_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT.parent.mkdir(parents=True, exist_ok=True)

    pdfs = [
        ROOT / "sample_report.pdf",
        Path(r"C:\Users\mwzah\Downloads\XXXXX3663_GSPrefdandHybridSecurties_2025.12_Statement.pdf"),
    ]
    pdfs = [p for p in pdfs if p.exists()]
    if not pdfs:
        raise FileNotFoundError("No benchmark PDFs found.")

    rows = []
    for pdf in pdfs:
        base = pdf.stem.lower().replace(" ", "_")
        classic_json = OUT_DIR / f"{base}_classic.json"
        hybrid_json = OUT_DIR / f"{base}_hybrid.json"

        classic_secs = _run([str(PY), str(RUN), "json", str(pdf), "-o", str(classic_json)])
        hybrid_secs = _run([str(PY), str(RUN), "hybrid", str(pdf), "-o", str(hybrid_json)])

        h_payload = _read_json(hybrid_json)
        h_meta = h_payload.get("meta", {})
        rows.append(
            {
                "pdf": pdf.name,
                "classic_wall_s": round(classic_secs, 2),
                "hybrid_wall_s": round(hybrid_secs, 2),
                "speedup_pct": round(((classic_secs - hybrid_secs) / classic_secs) * 100, 2) if classic_secs > 0 else None,
                "hybrid_bad_pages": h_meta.get("hybrid_bad_pages", []),
                "hybrid_vl_timing_s": h_meta.get("vl_timing_seconds"),
                "hybrid_vl_pages": h_meta.get("vl_page_numbers", []),
            }
        )

    lines = [
        "# Baseline Speed Profile",
        "",
        "This baseline captures wall-clock runtime for current pipeline modes.",
        "",
        "| PDF | Classic JSON (s) | Hybrid JSON (s) | Speedup vs Classic | Hybrid bad pages | Hybrid VL timing (s) | Hybrid VL pages |",
        "|---|---:|---:|---:|---|---:|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r['pdf']} | {r['classic_wall_s']} | {r['hybrid_wall_s']} | {r['speedup_pct']}% | {r['hybrid_bad_pages']} | {r['hybrid_vl_timing_s']} | {r['hybrid_vl_pages']} |"
        )

    lines.extend(
        [
            "",
            "## Notes",
            "- Classic = `run.py json` (library extraction only).",
            "- Hybrid = `run.py hybrid` (library first + VL on bad pages only).",
            "- This is the baseline before accuracy tuning changes.",
        ]
    )
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote baseline report: {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
