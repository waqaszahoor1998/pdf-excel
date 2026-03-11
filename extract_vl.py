#!/usr/bin/env python3
"""
PDF → extracted text/tables via a local vision-language model (Qwen2.5-VL-7B).

Use when PDFs are scanned or have little extractable text: render pages to images,
run VL on each image, return combined output. Fits into the existing pipeline as
PDF → (images) → VL → text/structure → canonical JSON → Excel.

Requires: pip install -r requirements-vl.txt
          python scripts/download_qwen2vl.py  (once, to download model + mmproj)

Env: QWEN2VL_MODEL_DIR (default: ./models/qwen2.5-vl-7b) or QWEN2VL_MODEL_PATH + QWEN2VL_MMPROJ_PATH
"""

import base64
import logging
import os
import sys
from pathlib import Path

log = logging.getLogger(__name__)

# Default filenames from ggml-org/Qwen2.5-VL-7B-Instruct-GGUF
MODEL_FILENAME = "Qwen2.5-VL-7B-Instruct-Q4_K_M.gguf"
MMPROJ_FILENAME = "mmproj-Qwen2.5-VL-7B-Instruct-f16.gguf"

DEFAULT_PROMPT = "Extract all text and tables from this document page. Preserve structure: sections, headers, and rows. Output the content clearly."


def _model_paths():
    """Resolve paths to main GGUF and mmproj from env."""
    root = Path(__file__).resolve().parent
    try:
        from dotenv import load_dotenv
        load_dotenv(root / ".env")
    except ImportError:
        pass

    model_path = os.environ.get("QWEN2VL_MODEL_PATH")
    mmproj_path = os.environ.get("QWEN2VL_MMPROJ_PATH")
    if model_path and mmproj_path:
        return Path(model_path).expanduser().resolve(), Path(mmproj_path).expanduser().resolve()

    model_dir = os.environ.get("QWEN2VL_MODEL_DIR")
    if not model_dir:
        model_dir = root / "models" / "qwen2.5-vl-7b"
    model_dir = Path(model_dir).expanduser().resolve()
    return model_dir / MODEL_FILENAME, model_dir / MMPROJ_FILENAME


def _ensure_cuda_path():
    """If llama-cpp-python was built with CUDA, its DLLs need CUDA runtime.
    The package uses CUDA_PATH for add_dll_directory(); set it before first import."""
    for candidate in (
        os.environ.get("CUDA_PATH"),
        r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v13.2",
        r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.8",
        r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.4",
    ):
        if not candidate:
            continue
        bin_dir = Path(candidate) / "bin"
        if bin_dir.exists():
            # Loader in llama_cpp uses CUDA_PATH for add_dll_directory(bin/lib)
            os.environ["CUDA_PATH"] = str(Path(candidate).resolve())
            path = os.environ.get("PATH", "")
            if str(bin_dir) not in path:
                os.environ["PATH"] = f"{bin_dir}{os.pathsep}{path}"
            break


def _load_llm():
    """Lazy-load the VL model and mmproj. Returns Llama instance."""
    _ensure_cuda_path()
    try:
        from llama_cpp import Llama
        from llama_cpp.llama_chat_format import Qwen25VLChatHandler
    except ImportError as e:
        raise ImportError(
            "Install VL dependencies: pip install -r requirements-vl.txt"
        ) from e

    model_path, mmproj_path = _model_paths()
    if not model_path.exists():
        raise FileNotFoundError(
            f"Model not found: {model_path}. Run: python scripts/download_qwen2vl.py"
        )
    if not mmproj_path.exists():
        raise FileNotFoundError(
            f"Mmproj not found: {mmproj_path}. Run: python scripts/download_qwen2vl.py"
        )

    log.info("Loading VL model %s and mmproj %s", model_path.name, mmproj_path.name)
    llm = Llama(
        model_path=str(model_path),
        mmproj=str(mmproj_path),
        n_ctx=4096,
        n_gpu_layers=-1,  # offload all to GPU if available
        verbose=False,
        chat_handler=Qwen25VLChatHandler(clip_model_path=str(mmproj_path), verbose=False),
    )
    return llm


def pdf_pages_to_images(pdf_path: str | Path, max_pages: int | None = None) -> list[bytes]:
    """
    Render PDF pages to PNG bytes. Uses PyMuPDF (fitz).
    Returns list of PNG image bytes, one per page (up to max_pages).
    """
    try:
        import fitz
    except ImportError:
        raise ImportError("PyMuPDF is required: pip install pymupdf") from None

    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {path}")

    doc = fitz.open(str(path))
    try:
        n = min(len(doc), max_pages) if max_pages else len(doc)
        images = []
        for i in range(n):
            page = doc[i]
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)  # 2x for readability
            images.append(pix.tobytes(output="png"))
        return images
    finally:
        doc.close()


def image_bytes_to_data_uri(png_bytes: bytes) -> str:
    """Encode PNG bytes as a data URI for the vision model."""
    b64 = base64.b64encode(png_bytes).decode("ascii")
    return f"data:image/png;base64,{b64}"


def run_vl_on_image(llm, image_data_uri: str, prompt: str = DEFAULT_PROMPT, max_tokens: int = 2048) -> str:
    """
    Run the VL model on one image and return the generated text.
    llm: Llama instance (with mmproj).
    """
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": image_data_uri}},
                {"type": "text", "text": prompt},
            ],
        }
    ]
    try:
        out = llm.create_chat_completion(
            messages=messages,
            max_tokens=max_tokens,
            temperature=0.1,
        )
    except Exception as e:
        log.warning("create_chat_completion failed (model may need different chat_format): %s", e)
        return ""
    choice = (out.get("choices") or [None])[0]
    if not choice:
        return ""
    msg = choice.get("message") or {}
    return (msg.get("content") or "").strip()


def extract_pdf_with_vl(
    pdf_path: str | Path,
    prompt: str = DEFAULT_PROMPT,
    max_pages: int | None = 10,
    llm=None,
) -> str:
    """
    Extract text from a PDF using the vision-language model: render pages to images,
    run VL on each, concatenate results. Use for scanned or low-text PDFs.

    Returns a single string with all extracted content (one block per page, separated).
    """
    images = pdf_pages_to_images(pdf_path, max_pages=max_pages)
    if not images:
        return ""

    if llm is None:
        llm = _load_llm()

    parts = []
    for i, png_bytes in enumerate(images):
        data_uri = image_bytes_to_data_uri(png_bytes)
        log.info("VL page %s/%s", i + 1, len(images))
        text = run_vl_on_image(llm, data_uri, prompt=prompt)
        if text:
            parts.append(f"--- Page {i + 1} ---\n{text}")
    return "\n\n".join(parts) if parts else ""


def main():
    """CLI: python -m extract_vl <pdf_path> [--prompt TEXT] [--max-pages N] [--out FILE]"""
    import argparse
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    parser = argparse.ArgumentParser(description="Extract content from PDF using Qwen2.5-VL (vision)")
    parser.add_argument("pdf_path", type=Path, help="Path to PDF")
    parser.add_argument("--prompt", default=DEFAULT_PROMPT, help="Prompt for each page")
    parser.add_argument("--max-pages", type=int, default=10, help="Max pages to process (default 10)")
    parser.add_argument("--out", type=Path, default=None, help="Write output to file instead of stdout")
    args = parser.parse_args()

    if not args.pdf_path.exists():
        print(f"Error: not found: {args.pdf_path}", file=sys.stderr)
        sys.exit(1)

    text = extract_pdf_with_vl(
        args.pdf_path,
        prompt=args.prompt,
        max_pages=args.max_pages,
    )
    if args.out:
        args.out.write_text(text, encoding="utf-8")
        print(f"Wrote {args.out}")
    else:
        print(text)


if __name__ == "__main__":
    main()
