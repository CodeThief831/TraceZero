"""Tests for document extractors and unified pipeline (fast & mocked neural modes)."""

from humanlens.detectors.neural import ClassifierScore
from humanlens.detectors.pipeline import analyze_document, analyze_file, analyze_text
from humanlens.extractors import extract_from_text, inspect_unicode_hygiene, normalize_extracted_text


class _FakeEnsemble:
    def score_text(self, text: str):
        score = 80.0 if "furthermore" in text.lower() else 4.0
        return [
            ClassifierScore("fakespot", "mock/fakespot", score),
            ClassifierScore("academic_det", "mock/academic", score * 0.5),
        ]


def test_unicode_hygiene_detection_and_normalization():
    sample = "Hello\u00a0world\u2011check\u200b."
    warnings = inspect_unicode_hygiene(sample)
    assert len(warnings) == 3
    assert normalize_extracted_text(sample) == "Hello world-check."


def test_fast_pipeline_without_weights():
    rep = analyze_text(
        "The team checked firewall logs first. Turns out an old test VM still had SSH open to the internet, "
        "so we pulled the rule right away and rotated the local admin password.",
        use_neural=False,
        use_perplexity=False,
    )
    assert rep.verdict == "Likely Human"
    assert rep.overall_ai_score < 15.0


def test_pipeline_with_mocked_neural_ensemble():
    doc = extract_from_text(
        "Furthermore, organizations should utilize robust encryption.\n\n"
        "We rotated every exposed key from a clean jump host right away."
    )
    rep = analyze_document(
        doc,
        use_neural=True,
        use_perplexity=False,
        ensemble=_FakeEnsemble(),
    )
    assert len(rep.sections) == 2
    assert rep.sections[0].ai_score > rep.sections[1].ai_score


def test_extract_pdf_roundtrip(tmp_path):
    import fitz

    pdf_path = tmp_path / "sample.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "This is a short sample PDF paragraph with enough words to extract cleanly.")
    doc.save(str(pdf_path))
    doc.close()

    rep = analyze_file(pdf_path, use_neural=False, use_perplexity=False)
    assert rep.source_name == "sample.pdf"
    assert rep.stylometry.word_count >= 10
