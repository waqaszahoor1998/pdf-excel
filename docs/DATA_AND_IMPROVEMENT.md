# How We Identify PDF Types, and Using More Data to Improve

This doc clarifies (1) how we tell broker vs tax vs universal apart, (2) why we don’t need “training data” for that, and (3) how you can use more PDFs and public datasets to improve extraction results.

---

## 1. How we identify “broker statement” vs “tax statement” vs “universal”

We **do not** use the vision model (Qwen 2.5 VL) to classify document type. We don’t need training data for this.

**What we do:** **Keyword-based detection** on **text** extracted from the first 1–2 pages of the PDF (using PyMuPDF).

- We have two lists of phrases in `extract_vl.py`: `DOC_TYPE_TAX_PHRASES` and `DOC_TYPE_BROKER_PHRASES`.
- We extract plain text from page 1 (and optionally page 2), combine it, lower-case it, and **count how many phrases from each list appear** in that text.
- If tax phrases win → we use the **tax_statement** prompt.
- If broker phrases win → we use the **broker_statement** prompt.
- Otherwise → we use the **universal** prompt.

So “identifying what those exactly are” is **rule-based string matching**, not a trained model. No training data is required. If you see new broker or tax documents that use different wording, you can **add more phrases** to those lists (e.g. “1099-DIV”, “cost basis”, “margin statement”) to improve detection.

---

## 2. The extraction model (Qwen 2.5 VL): pre-trained, not trained by us

The **table extraction** is done by the **local** Qwen 2.5 VL model. We use it **as-is** (pre-trained). We do **not** train or fine-tune it in this project.

- So we are **not** using your 1–2 PDFs as “training data” for the model.
- We **are** using your PDFs (and the prompts we wrote) to **design prompts** and **validate** that the output is good. Improving results here means: **better prompts**, **more tokens**, **post-processing**, and **evaluation on more documents** — not training the model (unless you decide to do that separately).

So: **Detection** = keyword rules (no training). **Extraction** = pre-trained VL + our prompts (no training in the current setup). “Training data” in the sense of “many labeled PDFs” is still useful for **evaluation** and, if you want to go there later, **fine-tuning**.

---

## 3. How more PDFs and data *do* help (without training the model)

You only have one or two broker/tax PDFs right now. Here’s how adding more PDFs and using public data helps:

| Use | How it helps |
|-----|----------------|
| **More PDFs of the same type** | Run our pipeline on them, inspect JSON/Excel vs the real PDF. Where it fails, **refine the prompt** (e.g. add the missing section names or column layout). No model training. |
| **Expand detection phrases** | When you see new broker or tax documents, note the exact headings (e.g. “Margin Summary”, “1099-DIV”). Add those to `DOC_TYPE_BROKER_PHRASES` or `DOC_TYPE_TAX_PHRASES` in `extract_vl.py` so future uploads of that style are classified correctly. |
| **Evaluation / benchmarking** | Use **public datasets** (see below) that have PDFs or images + ground-truth tables. Run our extractor, compare output to ground truth (e.g. cell overlap, row count). That tells you how good we are and where to improve prompts or logic. |
| **Few-shot in the prompt (optional)** | For a specific document type, you could add 1–2 short examples (e.g. “Example table: Title → Headers → Rows”) in the prompt so the model sees the desired format. Those examples are like “training data” only in the prompt; no model training. |
| **Fine-tuning (later, optional)** | If you eventually want the model itself to get better on your document types, you’d need many (image, target extraction) pairs and a fine-tuning pipeline. Public table datasets can be a starting point; see below. |

So: **you don’t need a big amount of training data to “identify” broker vs tax** — that’s keywords. To **improve extraction results**, the practical levers are: **more PDFs to tune and test prompts**, and **public datasets to evaluate** (and optionally, later, to fine-tune).

---

## 4. Scripts: download and run evaluation

We added two scripts so the project can **download** benchmark data and **run evaluation** with no extra manual steps:

| Script | What it does |
|--------|----------------|
| **`scripts/download_benchmark_data.py`** | Loads **OmniDocBench** from Hugging Face (downloads ~1.2 GB on first run). Optionally saves the first N images and a manifest to `data/benchmarks/OmniDocBench` for offline use. |
| **`scripts/run_benchmark_eval.py`** | Loads OmniDocBench (from cache or from a local dir), runs our **VL extractor** on up to N page images, and compares the number of detected tables to the ground truth. Prints a short summary and can write a report JSON. |

**Requirements:** `pip install datasets` (Hugging Face Datasets). The VL model must already be installed (e.g. you've run `python -m extract_vl` before).

**Example:**

```bash
# Download and cache OmniDocBench, and save first 20 images locally (optional)
python scripts/download_benchmark_data.py --samples 20 --out data/benchmarks/OmniDocBench

# Run evaluation on 5 samples (uses cached dataset or local dir)
python scripts/run_benchmark_eval.py --max-samples 5 --schema-type universal

# Run on local saved images and write report
python scripts/run_benchmark_eval.py --max-samples 10 --local data/benchmarks/OmniDocBench --out output/eval_report.json
```

So you can run these yourself to pull the data and improve results: the download script fetches the benchmark; the eval script runs our pipeline on it and reports how often we detect a table vs ground truth.

---

## 5. Public datasets useful for this project

These are suitable for **evaluation** (run our pipeline, compare to ground truth) and, if you go that route, **fine-tuning** or research. Most are not broker/tax-specific but are good for table extraction and document understanding in general.

| Dataset | What it is | How you can use it |
|--------|-------------|---------------------|
| **PubTables-1M** | ~1M tables from scientific articles; headers and cell locations. | Evaluate table extraction quality (e.g. run VL on page images, compare structure to annotations). Often used to train/fine-tune table detection models. |
| **PubTables-v2** | Large set with full-page and multi-page tables (500K+ tables). | Same as above; good for full-page and multi-page table evaluation. |
| **OmniDocBench** | 1,355 PDF pages, 9 document types (academic, financial reports, newspapers, etc.), layout + table + formula annotations. | Strong for **benchmarking**: run our extractor on their PDFs, compare to their ground truth (e.g. TEDS for tables). Not broker/tax-specific but includes financial reports. |
| **RD-TableBench** | 1,000 complex table images (scanned, handwriting, merged cells, multi-language). | Evaluate robustness of extraction on hard tables. |
| **DocVQA, CORD, SROIE** | Document VQA and receipt/invoice datasets (images + questions or key-value pairs). | More for “find this field” or form understanding; can still be used to test if our universal prompt gets useful structure from invoices/forms. |
| **SEC XBRL / Financial Statement datasets** | SEC filings (10-K, 10-Q) with structured financial data. | Useful for **financial** document context; usually already structured (XBRL). Good for inspiration or for building a separate “SEC-style” evaluation set. |

**Where to look:**  
- Hugging Face Datasets: search “document understanding”, “table extraction”, “PDF”.  
- Papers With Code: “Table Extraction”, “Document Understanding”.  
- GitHub: “PubTables”, “OmniDocBench”, “table recognition dataset”.

**Practical next step:** Pick one small benchmark (e.g. a subset of OmniDocBench or PubTables), run our VL extraction on it, and compute a simple metric (e.g. table detection yes/no, or cell match rate). That gives you a baseline to improve from when you refine prompts or add more PDFs.

---

## 6. If you want to add more of your own PDFs

- **Detection:** As you collect more broker or tax PDFs, note recurring titles and phrases (e.g. “Tax Year Summary”, “Margin Statement”). Add them to `DOC_TYPE_TAX_PHRASES` or `DOC_TYPE_BROKER_PHRASES` in `extract_vl.py`. That makes “identifying what those exactly are” more reliable without any model training.
- **Extraction:** Run the pipeline on each new PDF, then:
  - Manually compare JSON/Excel to the PDF.
  - If a section or table is wrong or missing, adjust the **prompt** (or add a doc-type-specific prompt) and re-run. Over time you get a small “test set” of your own PDFs to check after every change.

So: **we are not using your 1–2 PDFs as training data for the model.** We use keyword rules to identify broker vs tax vs universal. To get better results, **increase the number of PDFs you evaluate on** (your own + public datasets) and **improve prompts and detection phrases**; optional later step is **fine-tuning** with larger, labeled datasets.
