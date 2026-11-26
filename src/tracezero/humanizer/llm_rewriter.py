"""Optional detector-guided LLM paragraph rewriter (Ollama or OpenAI-compatible)."""

from __future__ import annotations

import os
import requests

SYSTEM_PROMPT = (
    "You are editing technical and academic prose so it reads like a real practitioner wrote it. "
    "Keep every factual detail, standard number, and technical term accurate. "
    "Avoid parallel rule-of-three lists, participial endings (', ensuring...', ', noting...'), "
    "em-dashes, and cliché transitions (furthermore, moreover, additionally, crucial, robust, leverage). "
    "Mix short direct sentences with longer practical explanations, and return ONLY the rewritten paragraph."
)


def rewrite_with_openai_compatible(
    paragraph: str,
    model: str = "llama3.1",
    base_url: str | None = None,
    api_key: str | None = None,
    timeout: int = 45,
) -> str:
    """Rewrite a single flagged paragraph via an OpenAI-compatible /v1/chat/completions API (e.g., Ollama)."""
    endpoint = (base_url or os.environ.get("TRACEZERO_LLM_BASE_URL") or "http://localhost:11434/v1").rstrip("/")
    key = api_key or os.environ.get("TRACEZERO_LLM_API_KEY") or os.environ.get("OPENAI_API_KEY") or "ollama"

    resp = requests.post(
        f"{endpoint}/chat/completions",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={
            "model": model,
            "temperature": 0.75,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Rewrite naturally:\n\n{paragraph}"},
            ],
        },
        timeout=timeout,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"].strip()
