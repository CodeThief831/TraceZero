"""Detection modules for neural classification, perplexity, stylometry, and plagiarism."""

from .pipeline import AnalysisReport, analyze_file, analyze_text
from .plagiarism import PlagiarismReport, SourceMatch, compare_against_corpus, compare_texts

__all__ = [
    "AnalysisReport",
    "PlagiarismReport",
    "SourceMatch",
    "analyze_file",
    "analyze_text",
    "compare_against_corpus",
    "compare_texts",
]
