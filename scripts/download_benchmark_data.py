#!/usr/bin/env python3
"""
Download benchmark datasets (e.g. OmniDocBench) from Hugging Face for evaluation.
Run once to cache the data; then run_benchmark_eval.py can use it.

Usage:
  python scripts/download_benchmark_data.py
  python scripts/download_benchmark_data.py --samples 20 --out data/benchmarks
"""

import argparse
import json
import sys
from pathlib import Path

# Project root
ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS = Path(__file__).resolve().parent

if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
from hf_windows_cache import apply_short_hf_home


def download_omnidocbench(samples: int | None = None, out_dir: Path | None = None) -> dict:
    """
    Load OmniDocBench from Hugging Face (downloads on first run).
    If out_dir is set, save the first `samples` images and a manifest there.
    Returns a small dict with stats (num_rows, saved_paths, etc.).
    """
    try:
        from datasets import DownloadConfig, load_dataset
    except ImportError:
        print("Install datasets: pip install datasets", file=sys.stderr)
        return {"error": "datasets not installed"}

    apply_short_hf_home()
    print("Loading opendatalab/OmniDocBench (this may download ~1.2 GB on first run)...")
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
    total = len(ds)
    print(f"Dataset has {total} samples.")

    result = {"dataset": "OmniDocBench", "total_rows": total, "saved": 0, "out_dir": str(out_dir) if out_dir else None}

    if out_dir is None or samples is None or samples <= 0:
        return result

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    images_dir = out_dir / "images"
    images_dir.mkdir(exist_ok=True)

    n = min(samples, total)
    manifest = []

    for i in range(n):
        row = ds[i]
        # Dataset may have "image" (PIL) or "image_path" or similar
        img = row.get("image")
        if img is None:
            continue
        # Save image
        path = images_dir / f"page_{i:04d}.png"
        if hasattr(img, "save"):
            img.save(path)
        else:
            Path(path).write_bytes(img)
        # Ground truth: count table blocks if present
        layout = row.get("layout_dets") or []
        if isinstance(layout, list):
            gt_tables = sum(1 for b in layout if isinstance(b, dict) and b.get("category_type") == "table")
        else:
            gt_tables = 0
        manifest.append({"index": i, "image_path": str(path), "gt_table_count": gt_tables})
        result["saved"] += 1

    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    result["manifest_path"] = str(manifest_path)
    print(f"Saved {result['saved']} images and manifest to {out_dir}")
    return result


def main():
    ap = argparse.ArgumentParser(description="Download benchmark data for table extraction evaluation")
    ap.add_argument("--samples", type=int, default=0, help="Save first N samples to disk (0 = only load/cache)")
    ap.add_argument("--out", type=Path, default=ROOT / "data" / "benchmarks" / "OmniDocBench", help="Output directory")
    args = ap.parse_args()
    stats = download_omnidocbench(samples=args.samples or None, out_dir=args.out if args.samples else None)
    if stats.get("error"):
        sys.exit(1)
    print("Done.", stats)


if __name__ == "__main__":
    main()
