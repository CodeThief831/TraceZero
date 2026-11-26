"""Causal LM Perplexity, GLTR predictability, and Fast-DetectGPT Z-score engine."""

from __future__ import annotations

import math
from dataclasses import dataclass

from ..config import resolve_model_source


@dataclass
class PerplexityMetrics:
    """Token-level predictability metrics from a causal language model."""

    perplexity: float
    top10_pct: float
    mean_log_rank: float
    fast_detect_z: float
    sentence_ppl_std: float


class PerplexityAuditor:
    """Lazy-loading DistilGPT2 auditor for perplexity and curvature scoring."""

    def __init__(self, model_key: str = "distilgpt2") -> None:
        self.model_key = model_key
        self._tok = None
        self._mod = None

    def _ensure_loaded(self) -> None:
        if self._tok is not None and self._mod is not None:
            return
        from transformers import AutoModelForCausalLM, AutoTokenizer

        src = resolve_model_source(self.model_key)
        self._tok = AutoTokenizer.from_pretrained(src)
        self._mod = AutoModelForCausalLM.from_pretrained(src).eval()

    def score_snippet(self, text: str) -> tuple[float, float, float, float] | None:
        """Return (perplexity, top10_pct, mean_log_rank, fast_detect_z) for one chunk."""
        import torch

        self._ensure_loaded()
        enc = self._tok(text, return_tensors="pt", truncation=True, max_length=1024)
        ids = enc["input_ids"]
        if ids.shape[1] < 8:
            return None

        with torch.no_grad():
            out = self._mod(ids, labels=ids)
            ppl = math.exp(float(out.loss.item()))
            logits = out.logits[0, :-1, :]
            targets = ids[0, 1:]
            log_probs = torch.log_softmax(logits, dim=-1)
            probs = torch.softmax(logits, dim=-1)

            tok_lp = log_probs.gather(-1, targets.unsqueeze(-1)).squeeze(-1)
            mean_lp = (probs * log_probs).sum(dim=-1)
            var_lp = (probs * (log_probs ** 2)).sum(dim=-1) - (mean_lp ** 2)
            z_curv = float(((tok_lp - mean_lp).sum() / torch.sqrt(var_lp.sum().clamp(min=1e-6))).item())

            sorted_idx = torch.argsort(logits, dim=-1, descending=True)
            ranks = (sorted_idx == targets.unsqueeze(-1)).nonzero(as_tuple=False)[:, 1]
            top10 = float((ranks < 10).float().mean().item()) * 100.0
            mlr = float(torch.log(ranks.float() + 1.0).mean().item())

        return ppl, top10, mlr, z_curv

    def analyze(self, text: str, sentences: list[str] | None = None) -> PerplexityMetrics | None:
        """Compute full document metrics plus sentence-level perplexity std."""
        base = self.score_snippet(text)
        if base is None:
            return None
        ppl, top10, mlr, z_curv = base

        sent_ppl_std = 0.0
        if sentences:
            vals: list[float] = []
            for s in sentences[:40]:
                if len(s.split()) >= 6:
                    res = self.score_snippet(s)
                    if res is not None:
                        vals.append(res[0])
            if len(vals) > 1:
                mean_v = sum(vals) / len(vals)
                sent_ppl_std = math.sqrt(sum((v - mean_v) ** 2 for v in vals) / len(vals))

        return PerplexityMetrics(
            perplexity=round(ppl, 2),
            top10_pct=round(top10, 1),
            mean_log_rank=round(mlr, 2),
            fast_detect_z=round(z_curv, 2),
            sentence_ppl_std=round(sent_ppl_std, 1),
        )
