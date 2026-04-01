# Baseline Speed Profile

This baseline captures wall-clock runtime for current pipeline modes.

| PDF | Classic JSON (s) | Hybrid JSON (s) | Speedup vs Classic | Hybrid bad pages | Hybrid VL timing (s) | Hybrid VL pages |
|---|---:|---:|---:|---|---:|---|
| sample_report.pdf | 26.83 | 2.02 | 92.48% | [] | None | [] |
| XXXXX3663_GSPrefdandHybridSecurties_2025.12_Statement.pdf | 16.03 | 8.42 | 47.48% | [] | None | [] |

## Notes
- Classic = `run.py json` (library extraction only).
- Hybrid = `run.py hybrid` (library first + VL on bad pages only).
- This is the baseline before accuracy tuning changes.
