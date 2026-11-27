"""Tests for the offline plagiarism & similarity checker, CLI command, and API."""

from pathlib import Path

from fastapi.testclient import TestClient
from typer.testing import CliRunner

from tracezero.cli import app as cli_app
from tracezero.detectors.plagiarism import compare_against_corpus, compare_texts
from tracezero.web.app import app as web_app

runner = CliRunner()
client = TestClient(web_app)


def test_plagiarism_detects_exact_copy_and_original_text():
    source = (
        "Zero-trust architectures enforce strict per-request identity validation across every microservice "
        "boundary rather than trusting traffic inside a traditional perimeter firewall."
    )
    copied = (
        "Modern security teams adopt this model globally. "
        "Zero-trust architectures enforce strict per-request identity validation across every microservice "
        "boundary rather than trusting traffic inside a traditional perimeter firewall."
    )
    original = (
        "Bakers ferment sourdough starter overnight at cool ambient kitchen temperatures so wild yeast "
        "cultures develop mild acidity before shaping loaves in the morning."
    )

    rep_copy = compare_texts(copied, {"NIST Reference": source}, ngram_size=5)
    assert rep_copy.overall_similarity_score >= 45.0
    assert rep_copy.source_matches[0].source_name == "NIST Reference"
    assert len(rep_copy.matched_passages) >= 1

    rep_clean = compare_texts(original, {"NIST Reference": source}, ngram_size=5)
    assert rep_clean.overall_similarity_score < 10.0
    assert rep_clean.originality_score > 90.0


def test_plagiarism_detects_self_repetition_without_external_refs():
    repeated = (
        "Distributed logging aggregates kernel audit events across regional data centers. "
        "Distributed logging aggregates kernel audit events across regional data centers."
    )
    rep = compare_texts(repeated, references={})
    assert rep.self_overlap_pct >= 40.0
    assert rep.overall_similarity_score >= 40.0


def test_compare_against_corpus_directory(tmp_path: Path):
    ref_dir = tmp_path / "refs"
    ref_dir.mkdir()
    shared = (
        "Quantum key distribution exploits photon polarization states so any third-party eavesdropper "
        "measurably disturbs transmission fidelity across the optical fiber channel."
    )
    (ref_dir / "source_paper.txt").write_text(shared, encoding="utf-8")
    cand = tmp_path / "submission.txt"
    cand.write_text(shared + "\nOriginal conclusion written separately by the student.", encoding="utf-8")

    rep = compare_against_corpus(cand, [ref_dir], ngram_size=5)
    assert rep.references_checked == 1
    assert rep.overall_similarity_score >= 40.0

    cli_res = runner.invoke(cli_app, ["plagiarism", str(cand), "--ref", str(ref_dir)])
    assert cli_res.exit_code == 0
    assert "TraceZero Plagiarism Audit" in cli_res.stdout


def test_api_plagiarism_endpoints():
    src = "Multi-factor hardware security tokens mitigate credential phishing across privileged enterprise accounts."
    resp = client.post(
        "/api/plagiarism",
        json={"text": src, "references": {"policy.txt": src}, "ngram_size": 5},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["overall_similarity_score"] >= 80.0
    assert data["source_matches"][0]["source_name"] == "policy.txt"
