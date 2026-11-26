"""Neural sequence-classification ensemble for AI-generated text detection."""

from __future__ import annotations

from dataclasses import dataclass

from ..config import MODEL_REGISTRY, resolve_model_source


@dataclass
class ClassifierScore:
    """Single detector model prediction."""

    model_key: str
    repo_id: str
    ai_probability: float  # 0.0 .. 100.0


class NeuralDetectorEnsemble:
    """Lazy-loaded ensemble of RoBERTa AI-vs-Human classifiers."""

    def __init__(self, model_keys: tuple[str, ...] = ("fakespot", "academic_det")) -> None:
        for k in model_keys:
            if k not in MODEL_REGISTRY or MODEL_REGISTRY[k].kind != "classifier":
                raise ValueError(f"Invalid classifier model key: {k}")
        self.model_keys = model_keys
        self._loaded: dict[str, tuple[object, object, int]] = {}

    def _ensure_loaded(self, key: str) -> tuple[object, object, int]:
        if key in self._loaded:
            return self._loaded[key]
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        src = resolve_model_source(key)
        tok = AutoTokenizer.from_pretrained(src)
        mod = AutoModelForSequenceClassification.from_pretrained(src).eval()

        ai_idx = 1
        for idx, label in mod.config.id2label.items():
            low = str(label).lower()
            if any(token in low for token in ("ai", "fake", "chatgpt", "machine")):
                ai_idx = int(idx)
        self._loaded[key] = (tok, mod, ai_idx)
        return self._loaded[key]

    def score_text(self, text: str) -> list[ClassifierScore]:
        """Run all configured classifiers on `text` using chunked averaging for long inputs."""
        import torch

        words = text.split()
        if len(words) < 6:
            return []

        chunks = [
            " ".join(words[i : i + 320])
            for i in range(0, len(words), 260)
            if len(words[i : i + 320]) >= 6
        ] or [text]

        results: list[ClassifierScore] = []
        for key in self.model_keys:
            tok, mod, ai_idx = self._ensure_loaded(key)
            chunk_probs: list[float] = []
            for ch in chunks:
                enc = tok(ch, return_tensors="pt", truncation=True, max_length=512)
                with torch.no_grad():
                    logits = mod(**enc).logits[0]
                    prob = float(torch.softmax(logits, dim=-1)[ai_idx].item()) * 100.0
                    chunk_probs.append(prob)
            avg_prob = sum(chunk_probs) / len(chunk_probs)
            results.append(
                ClassifierScore(
                    model_key=key,
                    repo_id=MODEL_REGISTRY[key].repo_id,
                    ai_probability=round(avg_prob, 1),
                )
            )
        return results
