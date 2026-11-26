"""Fast linguistic stylometry & AI-pattern auditing (zero model weights needed)."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

# Phrases strongly over-represented in unedited LLM outputs
AI_CLICHE_PATTERNS: tuple[str, ...] = (
    "delve",
    "tapestry",
    "crucial",
    "vital",
    "pivotal",
    "robust",
    "comprehensive",
    "leverage",
    "utilize",
    "facilitate",
    "foster",
    "underscore",
    "bolster",
    "holistic",
    "seamless",
    "seamlessly",
    "actionable",
    "proactive",
    "proactively",
    "streamline",
    "paramount",
    "intricate",
    "meticulous",
    "multifaceted",
    "empower",
    "safeguard",
    "moreover",
    "furthermore",
    "additionally",
    "in conclusion",
    "it is essential to",
    "it is important to",
    "plays a critical role",
    "plays a crucial role",
    "in today's fast-paced",
    "in the ever-evolving",
    "remains a critical",
    "under the hood",
)

CONTRACTIONS_RE = re.compile(
    r"\b(?:don't|doesn't|didn't|can't|couldn't|won't|wouldn't|isn't|aren't|"
    r"wasn't|weren't|haven't|hasn't|shouldn't|it's|that's|there's|what's|"
    r"who's|here's|they're|we're|you're|you'll|we'll|they'll|i'm|i've)\b",
    re.IGNORECASE,
)

TRIPLET_RE = re.compile(r"\b[A-Za-z][a-z]+,\s+[A-Za-z][a-z]+,\s+and\s+[A-Za-z][a-z]+\b")


@dataclass
class StylometryReport:
    """Statistical and structural markers computed from text."""

    word_count: int
    sentence_count: int
    avg_sentence_length: float
    sentence_length_std: float
    burstiness_cv: float
    min_sentence_length: int
    max_sentence_length: int
    contraction_count: int
    question_count: int
    em_dash_count: int
    triplet_count: int
    consecutive_same_starters: int
    ai_cliche_hits: list[str] = field(default_factory=list)
    heuristic_ai_risk: float = 0.0
    notes: list[str] = field(default_factory=list)


def split_sentences(text: str) -> list[str]:
    """Split text into sentences while avoiding common abbreviations and numbering."""
    cleaned = re.sub(
        r"\b(Rev|No|St|Dr|Mr|Mrs|Ms|Pvt|Ltd|Fig|e\.g|i\.e|vs|Inc|Prof)\.",
        r"\1<DOT>",
        text,
    )
    cleaned = re.sub(r"(\d+)\.", r"\1<DOT>", cleaned)
    parts = re.split(r"(?<=[.!?])\s+", cleaned)
    sentences: list[str] = []
    for part in parts:
        restored = part.replace("<DOT>", ".").strip()
        if len(restored.split()) >= 2:
            sentences.append(restored)
    return sentences


def analyze_stylometry(text: str) -> StylometryReport:
    """Evaluate sentence-length burstiness, clichés, triplets, and repetition."""
    words = text.split()
    sentences = split_sentences(text)
    lengths = [len(s.split()) for s in sentences] or [len(words)]

    mean_len = sum(lengths) / len(lengths)
    var = sum((n - mean_len) ** 2 for n in lengths) / len(lengths)
    std_len = math.sqrt(var)
    cv = std_len / mean_len if mean_len > 0 else 0.0

    low = text.lower()
    cliches = [
        phrase
        for phrase in AI_CLICHE_PATTERNS
        if re.search(r"\b" + re.escape(phrase) + r"\b", low)
    ]

    contractions = len(CONTRACTIONS_RE.findall(text))
    questions = sum(1 for s in sentences if s.endswith("?"))
    em_dashes = text.count("—")
    triplets = len(TRIPLET_RE.findall(text))

    starters = [s.split()[0].lower() for s in sentences if s.split()]
    consec_same = sum(1 for i in range(len(starters) - 1) if starters[i] == starters[i + 1])

    # Heuristic 0..100 AI stylometry score combining uniformity + clichés + synthetic quirks
    risk = 0.0
    notes: list[str] = []

    if len(sentences) >= 3:
        if cv < 0.35:
            risk += 32.0
            notes.append(f"Low sentence-length burstiness (CV={cv:.2f}; human prose typically > 0.45).")
        elif cv < 0.45:
            risk += 16.0
            notes.append(f"Moderate sentence-length burstiness (CV={cv:.2f}).")

    if cliches:
        risk += min(45.0, len(cliches) * 8.0)
        notes.append(f"AI-overused vocabulary detected: {', '.join(cliches[:6])}.")

    if em_dashes >= 3 and len(words) < 600:
        risk += min(15.0, em_dashes * 4.0)
        notes.append(f"High em-dash density ({em_dashes} em-dashes).")

    if triplets >= 3 and len(words) < 500:
        risk += min(12.0, triplets * 3.0)
        notes.append(f"Frequent parallel rule-of-three lists ({triplets} occurrences).")

    if len(words) >= 180 and contractions == 0:
        risk += 8.0
        notes.append("Zero natural contractions across long prose.")

    if consec_same >= 3:
        risk += min(10.0, consec_same * 2.5)
        notes.append(f"Repeated consecutive sentence starters ({consec_same} pairs).")

    return StylometryReport(
        word_count=len(words),
        sentence_count=len(sentences),
        avg_sentence_length=round(mean_len, 2),
        sentence_length_std=round(std_len, 2),
        burstiness_cv=round(cv, 3),
        min_sentence_length=min(lengths),
        max_sentence_length=max(lengths),
        contraction_count=contractions,
        question_count=questions,
        em_dash_count=em_dashes,
        triplet_count=triplets,
        consecutive_same_starters=consec_same,
        ai_cliche_hits=cliches,
        heuristic_ai_risk=round(min(100.0, risk), 1),
        notes=notes,
    )
