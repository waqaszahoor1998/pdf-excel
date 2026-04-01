# Reminder for next session

**When you're back:** run the benchmark download and evaluation to improve extraction.

1. **Install deps (once):**  
   `pip install -r requirements-benchmark.txt`

2. **Download benchmark data (optional; eval will cache it):**  
   `python scripts/download_benchmark_data.py --samples 20 --out data/benchmarks/OmniDocBench`

3. **Run evaluation:**  
   `python scripts/run_benchmark_eval.py --max-samples 10 --schema-type universal`

4. **Use the results** to tune prompts/code in `extract_vl.py` or `config/vl.json`, then re-run eval to check improvement.

See **docs/BENCHMARK_DATA_EXPLAINED.md** for what the data is and **docs/DATA_AND_IMPROVEMENT.md** for the full flow.
