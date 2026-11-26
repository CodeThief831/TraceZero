"""Model registry and local path resolution."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ModelSpec:
    """Metadata describing a Hugging Face model used by HumanLens."""

    key: str
    repo_id: str
    kind: str  # "classifier" or "causal_lm"
    description: str
    approx_mb: int


MODEL_REGISTRY: dict[str, ModelSpec] = {
    "fakespot": ModelSpec(
        key="fakespot",
        repo_id="fakespot-ai/roberta-base-ai-text-detection-v1",
        kind="classifier",
        description="Modern RoBERTa detector trained on multi-LLM vs human text.",
        approx_mb=475,
    ),
    "academic_det": ModelSpec(
        key="academic_det",
        repo_id="andreas122001/roberta-academic-detector",
        kind="classifier",
        description="RoBERTa detector tuned for academic and technical writing.",
        approx_mb=475,
    ),
    "chatgpt_roberta": ModelSpec(
        key="chatgpt_roberta",
        repo_id="Hello-SimpleAI/chatgpt-detector-roberta",
        kind="classifier",
        description="Lightweight RoBERTa baseline trained on HC3 human/ChatGPT pairs.",
        approx_mb=475,
    ),
    "distilgpt2": ModelSpec(
        key="distilgpt2",
        repo_id="distilbert/distilgpt2",
        kind="causal_lm",
        description="Causal LM used for perplexity, GLTR rank, and Fast-DetectGPT Z-score.",
        approx_mb=336,
    ),
}


def resolve_models_root() -> Path:
    """Return the models root directory, keeping weights separate from source."""
    env_dir = os.environ.get("HUMANLENS_MODELS_DIR")
    if env_dir:
        return Path(env_dir).expanduser().resolve()
    cwd_models = Path.cwd() / "models"
    if cwd_models.exists():
        return cwd_models
    pkg_repo_models = Path(__file__).resolve().parents[2] / "models"
    if pkg_repo_models.exists():
        return pkg_repo_models
    return Path.home() / ".cache" / "humanlens" / "models"


def resolve_model_source(key: str) -> str:
    """Return a local model folder path if downloaded, else the HF repo ID."""
    spec = MODEL_REGISTRY[key]
    local_dir = resolve_models_root() / key
    if local_dir.is_dir() and (
        (local_dir / "model.safetensors").exists() or (local_dir / "pytorch_model.bin").exists()
    ):
        return str(local_dir)
    return spec.repo_id


def is_model_cached_locally(key: str) -> bool:
    """Return True if model weights exist in the local models directory."""
    local_dir = resolve_models_root() / key
    return local_dir.is_dir() and (
        (local_dir / "model.safetensors").exists() or (local_dir / "pytorch_model.bin").exists()
    )
