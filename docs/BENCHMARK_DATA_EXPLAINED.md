# What Is the “Benchmark Data” and What Does the Download Do?

This doc explains what we’re actually downloading, what it’s for, and how it’s different from “a library of PDFs to improve universal extraction.”

---

## What you had in mind (one-time PDF library)

You were thinking of something like:

- **One-time download** of **many PDFs** (broker statements, tax docs, invoices, reports, etc.).
- Those PDFs would give you an **extensive overview** of different document types.
- You could **use those PDFs** to improve prompts and code for **universal** PDF extraction (e.g. run the pipeline on them, see what fails, tune prompts).

So: **data = a set of real PDFs** that you can open, run through the extractor, and use to make the system better for any PDF.

---

## What we actually set up (evaluation benchmark)

What’s in the project is different. It’s an **evaluation benchmark**, not a PDF library.

### What gets downloaded: **OmniDocBench**

- **Source:** Hugging Face dataset `opendatalab/OmniDocBench`.
- **What it is:**
  - **~1,355 page images** (pages that were rendered from PDFs and saved as images).
  - **Annotations (labels)** for each page: where the titles, text blocks, **tables**, figures, etc. are, and sometimes the table content (e.g. HTML).
- **So it’s not raw PDFs.** It’s **images + “ground truth” labels** (e.g. “this region is a table”).
- **Document types in the set:** academic papers, financial reports, newspapers, textbooks, handwritten notes, etc. So it’s diverse, but in the form of **images + labels**, not a folder of PDFs.

### What it’s used for

- **Evaluate** our extractor: run the VL model on those images, then **compare** our output (e.g. “we found 2 tables”) to the **ground truth** (“this page has 2 tables”).
- From that we get **numbers** (e.g. “we detect tables on 80% of pages where a table exists”). Those numbers tell us how good we are and **where** to improve (prompts, parsing, etc.).
- So the data helps **indirectly**: download → run evaluation → see results → use that to improve prompts/code. It does **not** give you a browseable set of PDFs to open and tune from.

### What each piece does

| Thing | What it does |
|-------|----------------|
| **`requirements-benchmark.txt`** | Lists Python packages needed for the benchmark scripts: `datasets` and `huggingface_hub`. You run `pip install -r requirements-benchmark.txt` **once** so the download and eval scripts can talk to Hugging Face and load the dataset. |
| **`scripts/download_benchmark_data.py`** | Calls Hugging Face and **loads OmniDocBench** (on first run it **downloads ~1.2 GB** of images + annotations and caches them). Optionally it can **save** the first N images and a small manifest (paths + ground-truth table count) into a folder like `data/benchmarks/OmniDocBench` so the eval script can use them without re-downloading. So “download” = **fetch this evaluation dataset** (images + labels), not “download a bunch of PDFs.” |
| **`scripts/run_benchmark_eval.py`** | Uses that data (from cache or from the folder above), runs **our VL extractor** on each image, and **compares** our output to the ground truth (e.g. table count). It prints a short summary and can write a report. So it tells you **how well** the current prompts/code do on a standard set of document pages. |

So in short:

- **requirements-benchmark.txt** = install deps for “download + run evaluation.”
- **download_benchmark_data.py** = **download the evaluation dataset** (OmniDocBench: images + labels), not a PDF library.
- That data **helps** by giving you a **measured baseline** so you can improve prompts/code in a targeted way; it does **not** replace the idea of “have a set of PDFs to look at and tune from.”

---

## How this fits with “improving universal extraction”

- **With the benchmark (what we have now):**  
  You run evaluation → see where the extractor fails (e.g. misses tables, wrong structure) → you then **change prompts or code** based on those results. The **data** is for **measuring**; the **improvement** still comes from you editing prompts/code (and maybe adding more detection phrases, etc.).

- **With a PDF library (what you had in mind):**  
  You’d have **many PDFs** (different types) on disk. You could open them, run the pipeline on them, and use them to **design** better prompts and logic for universal extraction. Right now we don’t have a script that “downloads a curated set of sample PDFs by type.” That would be a **different** kind of data and a different script (e.g. “sample PDFs for prompt tuning” or “diverse PDFs by category”).

---

## Summary

| Question | Answer |
|----------|--------|
| **What is the “data” we’re downloading?** | The **OmniDocBench dataset**: page **images** plus **annotations** (ground truth for layout/tables), not raw PDFs. |
| **What does “download benchmark data” do?** | It **downloads that evaluation dataset** (and optionally saves some images + a manifest) so we can run **run_benchmark_eval.py** and get a score. |
| **What is `requirements-benchmark.txt` for?** | So `pip install -r requirements-benchmark.txt` installs what’s needed to **download and run that evaluation** (Hugging Face `datasets` + `huggingface_hub`). |
| **Will this give me lots of PDFs to improve prompts?** | **No.** It gives you **images + labels** for **evaluation**. To improve universal extraction using “many different PDFs,” you’d want a **separate** set of **sample PDFs** (we could add a doc or script that points to or downloads those later). |

So: the benchmark download is for **evaluation** (measure how good we are); improving prompts and code for universal extraction still comes from **you** using that evaluation plus any **separate** set of PDFs you collect or we add for “sample documents by type.”
