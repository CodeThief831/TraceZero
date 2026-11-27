"""Typer + Rich CLI for TraceZero."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from . import __version__
from .config import MODEL_REGISTRY, is_model_cached_locally, resolve_models_root
from .detectors.pipeline import AnalysisReport, analyze_file, analyze_text
from .detectors.plagiarism import compare_against_corpus
from .downloader import download_model
from .extractors import extract_from_file
from .humanizer.rules import humanize_text

app = typer.Typer(
    name="tracezero",
    help="Local Multi-Model AI Text Detector, Perplexity Auditor & Humanization Workbench.",
    no_args_is_help=True,
)
console = Console()


def _render_report(report: AnalysisReport) -> None:
    color = (
        "green"
        if report.overall_ai_score < 15
        else "yellow"
        if report.overall_ai_score < 40
        else "red"
    )
    console.print(
        Panel.fit(
            f"[bold]{report.source_name}[/bold]\n"
            f"Overall AI Score: [{color} bold]{report.overall_ai_score:.1f}%[/{color} bold]  |  "
            f"Verdict: [{color}]{report.verdict}[/{color}]",
            title="TraceZero Analysis",
        )
    )

    if report.classifier_scores:
        t_clf = Table(title="Neural Classifier Ensemble")
        t_clf.add_column("Detector Key", style="cyan")
        t_clf.add_column("Hugging Face Model")
        t_clf.add_column("AI Probability", justify="right")
        for sc in report.classifier_scores:
            t_clf.add_row(sc.model_key, sc.repo_id, f"{sc.ai_probability:.1f}%")
        console.print(t_clf)

    st = report.stylometry
    t_meta = Table(title="Perplexity & Stylometry")
    t_meta.add_column("Metric", style="cyan")
    t_meta.add_column("Value", justify="right")
    t_meta.add_row("Words / Sentences", f"{st.word_count} / {st.sentence_count}")
    t_meta.add_row("Sentence Length (mean ± std, CV)", f"{st.avg_sentence_length} ± {st.sentence_length_std} (CV={st.burstiness_cv})")
    t_meta.add_row("Contractions / Em-dashes / Triplets", f"{st.contraction_count} / {st.em_dash_count} / {st.triplet_count}")
    t_meta.add_row("Stylometry Heuristic Risk", f"{st.heuristic_ai_risk:.1f}%")
    if report.perplexity:
        p = report.perplexity
        t_meta.add_row("DistilGPT2 Perplexity", f"{p.perplexity:.2f}")
        t_meta.add_row("Top-10 Token Predictability", f"{p.top10_pct:.1f}%")
        t_meta.add_row("Fast-DetectGPT Z-Score", f"{p.fast_detect_z:+.2f}")
    console.print(t_meta)

    if report.hygiene_warnings:
        console.print("[yellow]PDF / Encoding Hygiene Warnings:[/yellow]")
        for w in report.hygiene_warnings:
            console.print(f"  - {w}")

    if report.sections:
        t_sec = Table(title="Section / Page Breakdown")
        t_sec.add_column("Section", style="cyan")
        t_sec.add_column("Words", justify="right")
        t_sec.add_column("AI Score", justify="right")
        t_sec.add_column("Models")
        for s in report.sections:
            m_str = ", ".join(f"{k}={v:.1f}%" for k, v in s.model_scores.items())
            t_sec.add_row(s.label, str(s.word_count), f"{s.ai_score:.1f}%", m_str)
        console.print(t_sec)

    if report.flagged_sentences:
        console.print("[bold red]Top Flagged Sentences:[/bold red]")
        for idx, fl in enumerate(report.flagged_sentences[:6], 1):
            console.print(f"  {idx}. [{fl.ai_score:.1f}%] ({', '.join(fl.reasons)}) -> {fl.text}")


@app.command()
def version() -> None:
    """Show TraceZero version."""
    console.print(f"tracezero {__version__}")


@app.command()
def models() -> None:
    """List supported models and whether they are cached locally."""
    root = resolve_models_root()
    t = Table(title=f"TraceZero Models (root: {root})")
    t.add_column("Key", style="cyan")
    t.add_column("Kind")
    t.add_column("Size")
    t.add_column("Cached")
    t.add_column("Repository")
    for k, spec in MODEL_REGISTRY.items():
        cached = "[green]Yes[/green]" if is_model_cached_locally(k) else "[yellow]No[/yellow]"
        t.add_row(k, spec.kind, f"~{spec.approx_mb} MB", cached, spec.repo_id)
    console.print(t)


@app.command("download-models")
def download_models_cmd(
    keys: list[str] = typer.Argument(
        None,
        help="Model keys to download (default: fakespot academic_det distilgpt2).",
    ),
) -> None:
    """Download model weights into the local gitignored models/ directory."""
    targets = keys or ["fakespot", "academic_det", "distilgpt2"]
    for key in targets:
        console.print(f"Downloading [cyan]{key}[/cyan] ({MODEL_REGISTRY[key].repo_id})...")
        dest = download_model(key)
        console.print(f"[green]Saved to {dest}[/green]")


@app.command()
def scan(
    target: str = typer.Argument(..., help="Path to a .pdf, .docx, .txt, .md file, or raw string."),
    fast: bool = typer.Option(False, "--fast", help="Skip heavy neural/LM models; run stylometry & hygiene only."),
    no_ppl: bool = typer.Option(False, "--no-ppl", help="Skip DistilGPT2 perplexity scoring."),
    model: list[str] = typer.Option(["fakespot", "academic_det"], "--model", "-m", help="Classifier keys."),
    json_out: Optional[Path] = typer.Option(None, "--json-out", help="Write full JSON report to path."),
) -> None:
    """Scan a document or inline text for AI patterns, perplexity, and PDF hygiene."""
    p = Path(target)
    kwargs = {
        "models": tuple(model),
        "use_neural": not fast,
        "use_perplexity": (not fast) and (not no_ppl),
    }
    report = analyze_file(p, **kwargs) if p.exists() else analyze_text(target, **kwargs)
    _render_report(report)
    if json_out:
        json_out.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
        console.print(f"[green]Saved JSON report to {json_out}[/green]")


@app.command()
def humanize(
    target: str = typer.Argument(..., help="Path to file (.txt/.md/.pdf/.docx) or inline text."),
    out: Optional[Path] = typer.Option(None, "--out", "-o", help="Write humanized text to file."),
    fast: bool = typer.Option(False, "--fast", help="Use stylometry-only before/after check."),
) -> None:
    """Clean invisible PDF artifacts, replace AI clichés, and compare before/after scores."""
    p = Path(target)
    raw = extract_from_file(p).raw_text if p.exists() else target
    before = analyze_text(raw, use_neural=not fast, use_perplexity=False, score_sentences=False)
    res = humanize_text(raw)
    after = analyze_text(res.humanized_text, use_neural=not fast, use_perplexity=False, score_sentences=False)

    console.print(
        Panel.fit(
            f"Before AI Score: [red]{before.overall_ai_score:.1f}%[/red]  ->  "
            f"After AI Score: [green]{after.overall_ai_score:.1f}%[/green]",
            title="Humanizer Comparison",
        )
    )
    if res.changes_applied:
        for ch in res.changes_applied:
            console.print(f"  * {ch}")
    else:
        console.print("  No deterministic phrase or encoding changes needed.")

    if out:
        out.write_text(res.humanized_text, encoding="utf-8")
        console.print(f"[green]Saved humanized text to {out}[/green]")
    else:
        console.print("\n[bold]Humanized Output:[/bold]\n" + res.humanized_text)


@app.command()
def plagiarism(
    target: str = typer.Argument(..., help="Path to a .pdf, .docx, .txt, .md file, or raw string."),
    ref: list[Path] = typer.Option([], "--ref", "-r", help="Reference file(s) or folder(s) to compare against."),
    ngram: int = typer.Option(5, "--ngram", "-n", min=2, max=10, help="N-gram shingle width."),
    json_out: Optional[Path] = typer.Option(None, "--json-out", help="Write full JSON plagiarism report."),
) -> None:
    """Check a document or text for plagiarism, TF-IDF cosine overlap & self-repetition."""
    report = compare_against_corpus(target, ref_paths=ref, ngram_size=ngram)
    color = (
        "green"
        if report.overall_similarity_score < 10
        else "yellow"
        if report.overall_similarity_score < 35
        else "red"
    )
    console.print(
        Panel.fit(
            f"[bold]{report.candidate_name}[/bold] ({report.candidate_words} words, {report.references_checked} refs)\n"
            f"Similarity: [{color} bold]{report.overall_similarity_score:.1f}%[/{color} bold]  |  "
            f"Originality: [green]{report.originality_score:.1f}%[/green]  |  "
            f"Self-Overlap: {report.self_overlap_pct:.1f}%\n"
            f"Verdict: [{color}]{report.verdict}[/{color}]",
            title="TraceZero Plagiarism Audit",
        )
    )
    if report.source_matches:
        t_src = Table(title="Matched Reference Sources")
        t_src.add_column("Source", style="cyan")
        t_src.add_column("N-Gram Containment", justify="right")
        t_src.add_column("TF-IDF Cosine", justify="right")
        t_src.add_column("Combined", justify="right")
        for m in report.source_matches:
            t_src.add_row(
                m.source_name,
                f"{m.containment_pct:.1f}%",
                f"{m.cosine_similarity_pct:.1f}%",
                f"{m.combined_similarity_pct:.1f}%",
            )
        console.print(t_src)
    if report.matched_passages:
        console.print("[bold yellow]Top Overlapping Passages:[/bold yellow]")
        for idx, p_match in enumerate(report.matched_passages[:6], 1):
            console.print(f"  {idx}. [{p_match.similarity_pct:.1f}% vs {p_match.source_name}] {p_match.candidate_excerpt}")
    if json_out:
        json_out.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
        console.print(f"[green]Saved JSON plagiarism report to {json_out}[/green]")


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", help="Bind host."),
    port: int = typer.Option(8000, help="Bind port."),
) -> None:
    """Launch the interactive TraceZero Web UI (FastAPI)."""
    import uvicorn

    console.print(f"Starting TraceZero Web Workbench at [cyan]http://{host}:{port}[/cyan]")
    uvicorn.run("tracezero.web.app:app", host=host, port=port, reload=False)
