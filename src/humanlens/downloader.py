"""Direct HTTPS streaming downloader for Hugging Face models.

Avoids hf_xet/Xet-storage stalls on restricted or Windows networks by fetching
individual model artifacts directly over HTTPS.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

import requests

from .config import MODEL_REGISTRY, resolve_models_root

MODEL_FILES = (
    "config.json",
    "tokenizer.json",
    "tokenizer_config.json",
    "vocab.json",
    "merges.txt",
    "special_tokens_map.json",
    "model.safetensors",
)


def download_model(
    key: str,
    target_root: Path | None = None,
    progress_cb: Callable[[str, int, int], None] | None = None,
    timeout: int = 60,
) -> Path:
    """Download a registered model into `<target_root>/<key>`."""
    if key not in MODEL_REGISTRY:
        raise KeyError(f"Unknown model key '{key}'. Valid keys: {', '.join(MODEL_REGISTRY)}")

    spec = MODEL_REGISTRY[key]
    root = target_root or resolve_models_root()
    out_dir = root / key
    out_dir.mkdir(parents=True, exist_ok=True)

    for fname in MODEL_FILES:
        dest = out_dir / fname
        if dest.exists() and dest.stat().st_size > 100:
            continue
        url = f"https://huggingface.co/{spec.repo_id}/resolve/main/{fname}"
        resp = requests.get(url, stream=True, timeout=timeout, allow_redirects=True)
        if resp.status_code == 404 and fname != "model.safetensors":
            continue
        if resp.status_code == 404 and fname == "model.safetensors":
            url = f"https://huggingface.co/{spec.repo_id}/resolve/main/pytorch_model.bin"
            dest = out_dir / "pytorch_model.bin"
            resp = requests.get(url, stream=True, timeout=timeout, allow_redirects=True)
        resp.raise_for_status()

        total = int(resp.headers.get("content-length") or 0)
        written = 0
        tmp = dest.with_suffix(dest.suffix + ".part")
        with open(tmp, "wb") as fh:
            for chunk in resp.iter_content(chunk_size=1024 * 512):
                if chunk:
                    fh.write(chunk)
                    written += len(chunk)
                    if progress_cb:
                        progress_cb(fname, written, total)
        tmp.replace(dest)

    return out_dir
