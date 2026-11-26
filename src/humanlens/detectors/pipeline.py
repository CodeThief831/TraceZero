"""Unified detection pipeline combining neural classifiers, perplexity, and stylometry."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path

from ..extractors import ExtractedDocument, extract_from_file, extract_from_text
from .neural import ClassifierScore, NeuralDetectorEnsemble
from .perplexity import PerplexityAuditor, PerplexityMetrics
from .stylometry import StylometryReport, analyze_stylometry, split_sentences


@dataclass
class SectionFinding:
    """Per-section/page AI risk breakdown."""

    label: str
    word_count: int
    ai_score: float
    model_scores: dict[str, float]
    preview: str


@dataclass
class SentenceFlag:
    """Sentence-level risk flag for heatmaps and targeted rewriting."""

    text: str
    ai_score: float
    reasons: list[str] = field(default_factory=list)


@dataclass
class AnalysisReport:
    """Complete multi-signal AI detection and writing hygiene report."""

    source_name: str
    overall_ai_score: float
    verdict: str
    classifier_scores: list[ClassifierScore]
    perplexity: PerplexityMetrics | None
    stylometry: StylometryReport
    hygiene_warnings: list[str]
    sections: list[SectionFinding]
    flagged_sentences: list[SentenceFlag]

    def to_dict(self) -> dict:
        return asdict(self)


def _verdict_for(score: float) -> str:
    if score < 15.0:
        return "Likely Human"
    if score < 40.0:
        return "Mixed / Lightly Assisted"
    if score < 70.0:
        return "Uncertain / AI-Suspected"
    return "Likely AI-Generated"


def analyze_document(
    doc: ExtractedDocument,
    models: tuple[str, ...] = ("fakespot", "academic_det"),
    use_neural: bool = True,
    use_perplexity: bool = True,
    score_sentences: bool = True,
    ensemble: NeuralDetectorEnsemble | None = None,
    auditor: PerplexityAuditor | None = None,
) -> AnalysisReport:
    """Analyze an ExtractedDocument across all enabled signals."""
    text = doc.clean_text
    stylo = analyze_stylometry(text)
    sentences = split_sentences(text)

    ens: NeuralDetectorEnsemble | None = None
    if use_neural and models:
        ens = ensemble or NeuralDetectorEnsemble(models)

    clf_scores: list[ClassifierScore] = ens.score_text(text) if ens is not None else []

    ppl_metrics: PerplexityMetrics | None = None
    if use_perplexity:
        aud = auditor or PerplexityAuditor()
        ppl_metrics = aud.analyze(text, sentences=sentences if score_sentences else None)

    section_findings: list[SectionFinding] = []
    if ens is not None:
        for label, sec_txt in doc.sections:
            sec_scores = ens.score_text(sec_txt)
            if not sec_scores:
                continue
            avg_s = sum(s.ai_probability for s in sec_scores) / len(sec_scores)
            section_findings.append(
                SectionFinding(
                    label=label,
                    word_count=len(sec_txt.split()),
                    ai_score=round(avg_s, 1),
                    model_scores={s.model_key: s.ai_probability for s in sec_scores},
                    preview=(sec_txt[:140] + "...") if len(sec_txt) > 140 else sec_txt,
                )
            )
    else:
        for label, sec_txt in doc.sections:
            sec_st = analyze_stylometry(sec_txt)
            section_findings.append(
                SectionFinding(
                    label=label,
                    word_count=len(sec_txt.split()),
                    ai_score=sec_st.heuristic_ai_risk,
                    model_scores={"stylometry": sec_st.heuristic_ai_risk},
                    preview=(sec_txt[:140] + "...") if len(sec_txt) > 140 else sec_txt,
                )
            )

    flagged: list[SentenceFlag] = []
    if score_sentences:
        for sent in sentences[:60]:
            if len(sent.split()) < 7:
                continue
            reasons: list[str] = []
            s_stylo = analyze_stylometry(sent)
            if s_stylo.ai_cliche_hits:
                reasons.append(f"cliché: {', '.join(s_stylo.ai_cliche_hits)}")
            if s_stylo.em_dash_count > 0:
                reasons.append("em-dash")
            if s_stylo.triplet_count > 0:
                reasons.append("rule-of-three triplet")

            score_val = s_stylo.heuristic_ai_risk
            if ens is not None:
                sc = ens.score_text(sent)
                if sc:
                    # Weight primary detector heavily on short single sentences
                    score_val = max(s["ai_probability"] if isinstance(s, dict) else s.ai_probability for s in sc)
            if score_val >= 25.0 or reasons:
                flagged.append(
                    SentenceFlag(
                        text=sent,
                        ai_score=round(score_val, 1),
                        reasons=reasons or ["high neural classifier probability"],
                    )
                )
        flagged.sort(key=lambda f: f.ai_score, reverse=True)

    # Combine ensemble classifiers + section peaks + stylometry + Fast-DetectGPT Z-score
    if clf_scores:
        # Weight fakespot slightly higher if both present since academic_det is strict on academic style
        weights = {"fakespot": 0.65, "academic_det": 0.25, "chatgpt_roberta": 0.10}
        w_sum = sum(weights.get(s.model_key, 0.3) for s in clf_scores)
        clf_avg = sum(s.ai_probability * weights.get(s.model_key, 0.3) for s in clf_scores) / w_sum
        sec_peak = max((sf.ai_score for sf in section_findings), default=clf_avg)
        overall = 0.72 * clf_avg + 0.18 * sec_peak + 0.10 * stylo.heuristic_ai_risk
    else:
        overall = stylo.heuristic_ai_risk

    if ppl_metrics and ppl_metrics.fast_detect_z > 1.0:
        overall = min(100.0, overall + min(15.0, ppl_metrics.fast_detect_z * 5.0))

    overall = round(min(100.0, max(0.0, overall)), 1)

    return AnalysisReport(
        source_name=doc.source_name,
        overall_ai_score=overall,
        verdict=_verdict_for(overall),
        classifier_scores=clf_scores,
        perplexity=ppl_metrics,
        stylometry=stylo,
        hygiene_warnings=doc.hygiene_warnings,
        sections=section_findings,
        flagged_sentences=flagged[:15],
    )


def analyze_text(text: str, **kwargs) -> AnalysisReport:
    """Analyze inline prose."""
    return analyze_document(extract_from_text(text), **kwargs)


def analyze_file(path: str | Path, **kwargs) -> AnalysisReport:
    """Extract and analyze a .pdf, .docx, .txt, or .md file."""
    return analyze_document(extract_from_file(path), **kwargs)
