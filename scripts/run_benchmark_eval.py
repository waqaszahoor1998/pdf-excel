#!/usr/bin/env python3
"""
Run the VL extractor on benchmark dataset images and compare to ground truth.
Downloads OmniDocBench from Hugging Face on first run (or uses data from download_benchmark_data.py).

Usage:
  python scripts/run_benchmark_eval.py --max-samples 10
  python scripts/run_benchmark_eval.py --max-samples 5 --schema-type universal
"""

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from hf_windows_cache import apply_short_hf_home


def run_eval(max_samples: int = 10, schema_type: str | None = None, use_local: Path | None = None) -> dict:
    """
    Load benchmark data, run our VL extractor on each image, compare to ground truth.
    Returns dict with metrics (e.g. table_detection_match, section_counts).
    """
    from extract_vl import extract_single_image_to_sections

    results = []
    gt_table_counts = []
    pred_table_counts = []

    if use_local and Path(use_local).exists():
        manifest_path = Path(use_local) / "manifest.json"
        if not manifest_path.exists():
            print(f"No manifest at {manifest_path}", file=sys.stderr)
            return {"error": "missing manifest"}
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        samples = manifest[:max_samples]
        for item in samples:
            img_path = item.get("image_path")
            gt = item.get("gt_table_count", 0)
            if not img_path or not Path(img_path).exists():
                continue
            try:
                sections = extract_single_image_to_sections(img_path, schema_type=schema_type or "universal")
                # Count sections that look like tables (have headings and rows)
                pred_tables = sum(1 for s in sections if (s.get("headings") or s.get("rows")) and s.get("name") != "Extracted")
                if not pred_tables and sections:
                    pred_tables = len(sections)
                results.append({"path": img_path, "gt_tables": gt, "pred_tables": pred_tables, "sections": len(sections)})
                gt_table_counts.append(gt)
                pred_table_counts.append(pred_tables)
            except Exception as e:
                results.append({"path": img_path, "error": str(e), "gt_tables": gt})
                gt_table_counts.append(gt)
                pred_table_counts.append(0)
    else:
        try:
            from datasets import DownloadConfig, load_dataset
        except ImportError:
            print("Install datasets: pip install datasets", file=sys.stderr)
            return {"error": "datasets not installed"}

        hf_root = apply_short_hf_home()
        if hf_root and os.name == "nt":
            print(f"Using HF_HOME={hf_root} (short cache; avoids Windows path-length errors).", file=sys.stderr)
        print("Loading opendatalab/OmniDocBench...")
        # Short HF_HOME + num_proc=1 avoids Windows MAX_PATH / parallel download issues with long image names.
        dc = DownloadConfig(num_proc=1)
        try:
            ds = load_dataset("opendatalab/OmniDocBench", split="train", download_config=dc)
        except Exception as e:
            err = str(e).lower()
            if "trust_remote_code" in err or "loading script" in err:
                ds = load_dataset(
                    "opendatalab/OmniDocBench",
                    split="train",
                    trust_remote_code=True,
                    download_config=dc,
                )
            else:
                raise
        n = min(max_samples, len(ds))

        for i in range(n):
            row = ds[i]
            img = row.get("image")
            if img is None:
                continue
            gt_tables = 0
            layout = row.get("layout_dets") if "layout_dets" in row else (row.get("layout_dets") if hasattr(row, "get") else [])
            if isinstance(layout, list):
                gt_tables = sum(1 for b in layout if isinstance(b, dict) and b.get("category_type") == "table")

            try:
                sections = extract_single_image_to_sections(img, schema_type=schema_type or "universal")
                pred_tables = sum(1 for s in sections if (s.get("headings") or s.get("rows")) and s.get("name") != "Extracted")
                if not pred_tables and sections:
                    pred_tables = len(sections)
                results.append({"index": i, "gt_tables": gt_tables, "pred_tables": pred_tables, "sections": len(sections)})
                gt_table_counts.append(gt_tables)
                pred_table_counts.append(pred_tables)
            except Exception as e:
                results.append({"index": i, "error": str(e), "gt_tables": gt_tables})
                gt_table_counts.append(gt_tables)
                pred_table_counts.append(0)
            print(f"  Sample {i+1}/{n}: gt_tables={gt_tables}, pred_tables={results[-1].get('pred_tables', 0)}")

    # Simple metrics
    total_gt = sum(gt_table_counts)
    total_pred = sum(pred_table_counts)
    match = sum(1 for g, p in zip(gt_table_counts, pred_table_counts) if (g > 0) == (p > 0))  # both have tables or both don't
    n_eval = len(gt_table_counts)

    report = {
        "n_eval": n_eval,
        "total_gt_tables": total_gt,
        "total_pred_tables": total_pred,
        "table_detection_match": match,
        "table_detection_match_ratio": round(match / n_eval, 4) if n_eval else 0,
        "results": results,
    }
    return report


def main():
    ap = argparse.ArgumentParser(description="Evaluate VL extractor on benchmark dataset")
    ap.add_argument("--max-samples", type=int, default=5, help="Max number of samples to run (default 5)")
    ap.add_argument("--schema-type", type=str, default=None, help="Prompt profile: universal, broker_statement, tax_statement")
    ap.add_argument("--local", type=Path, default=None, help="Use local benchmark dir (e.g. data/benchmarks/OmniDocBench)")
    ap.add_argument("--out", type=Path, default=None, help="Write report JSON here")
    args = ap.parse_args()

    report = run_eval(max_samples=args.max_samples, schema_type=args.schema_type, use_local=args.local)
    if report.get("error"):
        print(report["error"], file=sys.stderr)
        sys.exit(1)

    print("\n--- Summary ---")
    print(f"Samples evaluated: {report['n_eval']}")
    print(f"Ground truth tables (total): {report['total_gt_tables']}")
    print(f"Predicted tables (total): {report['total_pred_tables']}")
    print(f"Table detection match (page-level): {report['table_detection_match']}/{report['n_eval']} ({report['table_detection_match_ratio']})")

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        # Don't write full results to keep file small; or write summary only
        summary = {k: v for k, v in report.items() if k != "results"}
        summary["sample_results_count"] = len(report.get("results", []))
        out_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(f"Wrote summary to {out_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
