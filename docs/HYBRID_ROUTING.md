# Hybrid Routing (Current)

This note explains how `run.py hybrid` decides when to use classic libraries vs VL model extraction.

## Flow

1. Run library extraction on all pages (`pdfplumber`/`PyMuPDF` path).
2. Score page quality from extracted sections.
3. Route low-quality pages to VL.
4. For routed pages, compare library vs VL page quality and keep the better source.
5. Merge final sections and write JSON.

## Routing Rule

A page is routed to VL if any of these are true:

- No section on that page is table-like.
- Page quality score is below threshold (`hybrid_quality_threshold`, currently `0.72`).
- Severe signal combination is present:
  - suspicious section names + null-heavy rows, or
  - suspicious section names + weak structure, or
  - null-heavy rows + weak structure.

## Page Quality Signals

The scorer uses:

- table-like ratio
- structured section ratio (multi-row/multi-column)
- null-heavy ratio (too many empty cells)
- suspicious section-name ratio (fragmented/noisy names like `_1`, broken period text)
- prose-heavy row ratio

Higher score means better quality.

## Winner Selection On Routed Pages

After VL runs on routed pages:

- compute library page quality and VL page quality
- default: keep VL
- keep library only if it is clearly better (`library_quality > vl_quality + margin`) and library quality is acceptable
- guardrail: if library names are mostly suspicious and VL names are cleaner, do **not** fallback to library

This prevents noisy library output from replacing better VL output.

## Metadata To Inspect In Output JSON

Look under `meta`:

- `hybrid_bad_pages`: pages initially routed to VL
- `hybrid_quality_threshold`: threshold used
- `hybrid_page_routing`: per-page score and route reasons
- `hybrid_selected_source_by_page`: final source for routed pages (`vl` or `library_fallback`)
- `hybrid_page_quality_compare`: library vs VL scores per routed page
- `hybrid_library_fallback_pages`: routed pages that finally used library
- `vl_timing_seconds`, `vl_per_page_seconds`, `vl_page_numbers`, `vl_page_timings`

## Practical Tuning

- Increase threshold (e.g. `0.72 -> 0.75`) to route more pages to VL (higher accuracy potential, slower).
- Decrease threshold to route fewer pages to VL (faster, more risk on hard pages).
- Keep guardrail enabled to avoid fallback to suspicious library names.
