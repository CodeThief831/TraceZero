"""Offline cross-document plagiarism, TF-IDF cosine similarity & self-overlap checker."""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path

from ..extractors import extract_from_file, normalize_extracted_text
from .stylometry import split_sentences

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_SUPPORTED_EXTS = {".pdf", ".docx", ".txt", ".md"}


@dataclass
class MatchedPassage:
    """Overlapping excerpt found between the candidate text and a reference source."""

    source_name: str
    candidate_excerpt: str
    similarity_pct: float
    matched_tokens: int


@dataclass
class SourceMatch:
    """Similarity metrics against a single reference source."""

    source_name: str
    containment_pct: float
    cosine_similarity_pct: float
    combined_similarity_pct: float
    matched_shingles: int
    total_candidate_shingles: int


@dataclass
class PlagiarismReport:
    """Unified offline plagiarism & originality report."""

    candidate_name: str
    candidate_words: int
    references_checked: int
    overall_similarity_score: float
    originality_score: float
    verdict: str
    source_matches: list[SourceMatch] = field(default_factory=list)
    matched_passages: list[MatchedPassage] = field(default_factory=list)
    self_overlap_pct: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(normalize_extracted_text(text).lower())


def _shingles(tokens: list[str], n: int) -> list[tuple[str, ...]]:
    if len(tokens) < n:
        return [tuple(tokens)] if tokens else []
    return [tuple(tokens[i : i + n]) for i in range(len(tokens) - n + 1)]


def _tfidf_cosine(doc_a: list[str], doc_b: list[str], idf: dict[str, float]) -> float:
    if not doc_a or not doc_b:
        return 0.0
    ca, cb = Counter(doc_a), Counter(doc_b)
    len_a, len_b = len(doc_a), len(doc_b)
    dot = 0.0
    norm_a = 0.0
    norm_b = 0.0
    for term, cnt in ca.items():
        w = (cnt / len_a) * idf.get(term, 1.0)
        norm_a += w * w
        if term in cb:
            wb = (cb[term] / len_b) * idf.get(term, 1.0)
            dot += w * wb
    for term, cnt in cb.items():
        wb = (cnt / len_b) * idf.get(term, 1.0)
        norm_b += wb * wb
    denom = math.sqrt(norm_a) * math.sqrt(norm_b)
    return (dot / denom) if denom > 0 else 0.0


def _verdict_for(score: float) -> str:
    if score < 10.0:
        return "Original / Minimal Overlap"
    if score < 25.0:
        return "Low / Moderate Similarity"
    if score < 55.0:
        return "Moderate Plagiarism Risk"
    return "High Plagiarism / Heavy Overlap"


def _compute_self_overlap(text: str, n: int = 5) -> float:
    """Measure internal repeated shingling / duplicate copy-pasted passages within text."""
    sents = [s for s in split_sentences(text) if len(_tokenize(s)) >= n]
    if len(sents) < 2:
        return 0.0
    seen: set[tuple[str, ...]] = set()
    dup_count = 0
    total = 0
    for sent in sents:
        toks = _tokenize(sent)
        sh = _shingles(toks, n)
        total += len(sh)
        for gram in sh:
            if gram in seen:
                dup_count += 1
        seen.update(sh)
    return round((dup_count / total) * 100.0, 1) if total else 0.0


def compare_texts(
    candidate_text: str,
    references: dict[str, str],
    candidate_name: str = "Input Document",
    ngram_size: int = 5,
) -> PlagiarismReport:
    """Compare candidate prose against reference sources using n-gram shingling and TF-IDF."""
    cand_tokens = _tokenize(candidate_text)
    if not cand_tokens:
        return PlagiarismReport(
            candidate_name=candidate_name,
            candidate_words=0,
            references_checked=len(references),
            overall_similarity_score=0.0,
            originality_score=100.0,
            verdict=_verdict_for(0.0),
        )

    eff_n = min(ngram_size, max(2, len(cand_tokens)))
    cand_shingles = _shingles(cand_tokens, eff_n)
    cand_shingle_set = set(cand_shingles)
    self_overlap = _compute_self_overlap(candidate_text, n=min(5, max(3, len(cand_tokens) // 3)))

    ref_tokens_map: dict[str, list[str]] = {
        name: _tokenize(txt) for name, txt in references.items() if txt and txt.strip()
    }

    # Build IDF across candidate + all references
    all_docs = [cand_tokens, *ref_tokens_map.values()]
    n_docs = len(all_docs)
    df: Counter[str] = Counter()
    for d in all_docs:
        df.update(set(d))
    idf = {term: math.log((1.0 + n_docs) / (1.0 + freq)) + 1.0 for term, freq in df.items()}

    source_matches: list[SourceMatch] = []
    matched_passages: list[MatchedPassage] = []
    matched_global_shingles: set[tuple[str, ...]] = set()

    cand_sentences = [s for s in split_sentences(candidate_text) if len(_tokenize(s)) >= 4]

    for ref_name, ref_toks in ref_tokens_map.items():
        if not ref_toks:
            continue
        ref_shingle_set = set(_shingles(ref_toks, eff_n))
        shared = cand_shingle_set & ref_shingle_set
        matched_global_shingles.update(shared)

        containment = (len(shared) / len(cand_shingle_set) * 100.0) if cand_shingle_set else 0.0
        cosine = _tfidf_cosine(cand_tokens, ref_toks, idf) * 100.0
        combined = round(0.65 * containment + 0.35 * cosine, 1)

        source_matches.append(
            SourceMatch(
                source_name=ref_name,
                containment_pct=round(containment, 1),
                cosine_similarity_pct=round(cosine, 1),
                combined_similarity_pct=combined,
                matched_shingles=len(shared),
                total_candidate_shingles=len(cand_shingle_set),
            )
        )

        # Sentence-level evidence extraction
        for sent in cand_sentences:
            s_toks = _tokenize(sent)
            s_n = min(eff_n, len(s_toks))
            s_shingles = set(_shingles(s_toks, s_n))
            sent_shared = s_shingles & (ref_shingle_set if s_n == eff_n else set(_shingles(ref_toks, s_n)))
            sent_shingle_pct = (len(sent_shared) / len(s_shingles) * 100.0) if s_shingles else 0.0
            sent_cos = _tfidf_cosine(s_toks, ref_toks, idf) * 100.0
            sent_score = max(sent_shingle_pct, sent_cos if len(s_toks) >= 7 else sent_shingle_pct)
            if sent_score >= 35.0:
                matched_passages.append(
                    MatchedPassage(
                        source_name=ref_name,
                        candidate_excerpt=sent[:240] + ("..." if len(sent) > 240 else ""),
                        similarity_pct=round(min(100.0, sent_score), 1),
                        matched_tokens=len(set(s_toks) & set(ref_toks)),
                    )
                )

    source_matches.sort(key=lambda m: m.combined_similarity_pct, reverse=True)
    matched_passages.sort(key=lambda p: p.similarity_pct, reverse=True)

    # Aggregate similarity: global shingle union containment + peak TF-IDF cosine, plus self-overlap if no refs
    if source_matches:
        global_contain = (len(matched_global_shingles) / len(cand_shingle_set) * 100.0) if cand_shingle_set else 0.0
        peak_cosine = max(m.cosine_similarity_pct for m in source_matches)
        overall = round(min(100.0, 0.68 * global_contain + 0.32 * peak_cosine), 1)
    else:
        overall = round(min(100.0, self_overlap), 1)

    return PlagiarismReport(
        candidate_name=candidate_name,
        candidate_words=len(cand_tokens),
        references_checked=len(ref_tokens_map),
        overall_similarity_score=overall,
        originality_score=round(max(0.0, 100.0 - overall), 1),
        verdict=_verdict_for(overall),
        source_matches=source_matches,
        matched_passages=matched_passages[:15],
        self_overlap_pct=self_overlap,
    )


def _expand_reference_paths(ref_paths: list[str | Path]) -> list[Path]:
    files: list[Path] = []
    for raw in ref_paths:
        p = Path(raw)
        if not p.exists():
            raise FileNotFoundError(f"Reference path not found: {p}")
        if p.is_dir():
            for child in sorted(p.rglob("*")):
                if child.is_file() and child.suffix.lower() in _SUPPORTED_EXTS:
                    files.append(child)
        elif p.is_file():
            files.append(p)
    return files


def compare_against_corpus(
    target: str | Path,
    ref_paths: list[str | Path] | None = None,
    ngram_size: int = 5,
) -> PlagiarismReport:
    """Run plagiarism check on a file or inline text against reference files/directories."""
    p = Path(target)
    if p.exists() and p.is_file():
        doc = extract_from_file(p)
        cand_text = doc.clean_text
        cand_name = doc.source_name
        cand_resolved = p.resolve()
    else:
        cand_text = normalize_extracted_text(str(target))
        cand_name = "Inline Input"
        cand_resolved = None

    references: dict[str, str] = {}
    for ref_file in _expand_reference_paths(ref_paths or []):
        if cand_resolved and ref_file.resolve() == cand_resolved:
            continue
        ref_doc = extract_from_file(ref_file)
        references[ref_doc.source_name] = ref_doc.clean_text

    return compare_texts(
        cand_text,
        references=references,
        candidate_name=cand_name,
        ngram_size=ngram_size,
    )
