"""Tests for stylometry auditing and deterministic humanizer rules."""

from tracezero.detectors.stylometry import analyze_stylometry, split_sentences
from tracezero.humanizer.rules import humanize_text


def test_split_sentences_preserves_abbreviations():
    txt = "NIST SP 800-53 Rev. 5 defines controls. Dr. Smith checked Fig. 2 carefully. Did it pass?"
    sents = split_sentences(txt)
    assert len(sents) == 3
    assert sents[0].startswith("NIST SP 800-53 Rev. 5")


def test_stylometry_flags_ai_cliches_and_low_burstiness():
    ai_like = (
        "Furthermore, it is crucial to leverage robust solutions in today's fast-paced world. "
        "Additionally, organizations must utilize comprehensive frameworks to facilitate seamless alignment. "
        "Moreover, proactive monitoring plays a critical role to bolster overall security."
    )
    rep = analyze_stylometry(ai_like)
    assert "furthermore" in rep.ai_cliche_hits
    assert "crucial" in rep.ai_cliche_hits
    assert "leverage" in rep.ai_cliche_hits
    assert rep.heuristic_ai_risk >= 40.0


def test_humanizer_cleans_unicode_cliches_and_em_dashes():
    dirty = (
        "Furthermore,\u00a0it is crucial to leverage a robust\u2011style system\u2014and "
        "ensure that teams do not ignore alerts."
    )
    res = humanize_text(dirty)
    assert "\u00a0" not in res.humanized_text
    assert "\u2011" not in res.humanized_text
    assert "—" not in res.humanized_text
    assert "furthermore" not in res.humanized_text.lower()
    assert "leverage" not in res.humanized_text.lower()
    assert "don't" in res.humanized_text.lower()
    assert len(res.changes_applied) >= 3
