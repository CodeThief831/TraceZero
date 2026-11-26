"""FastAPI backend for the TraceZero Web Workbench."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from .. import __version__
from ..config import MODEL_REGISTRY, is_model_cached_locally
from ..detectors.neural import NeuralDetectorEnsemble
from ..detectors.perplexity import PerplexityAuditor
from ..detectors.pipeline import analyze_document
from ..extractors import extract_from_text, inspect_unicode_hygiene, normalize_extracted_text, split_paragraphs
from ..humanizer.rules import humanize_text

app = FastAPI(title="TraceZero", version=__version__)
INDEX_HTML = Path(__file__).with_name("index.html")


class TextPayload(BaseModel):
    text: str
    use_neural: bool = True
    use_perplexity: bool = False
    models: list[str] = ["fakespot", "academic_det"]


class HumanizePayload(BaseModel):
    text: str
    add_contractions: bool = True
    soften_em_dashes: bool = True
    rescore_neural: bool = True


@lru_cache(maxsize=4)
def _get_ensemble(models_tuple: tuple[str, ...]) -> NeuralDetectorEnsemble:
    return NeuralDetectorEnsemble(models_tuple)


@lru_cache(maxsize=1)
def _get_auditor() -> PerplexityAuditor:
    return PerplexityAuditor()


@app.get("/", response_class=HTMLResponse)
def home() -> HTMLResponse:
    return HTMLResponse(INDEX_HTML.read_text(encoding="utf-8"))


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "version": __version__,
        "models": {k: is_model_cached_locally(k) for k in MODEL_REGISTRY},
    }


@app.post("/api/scan")
def api_scan(payload: TextPayload) -> dict:
    if not payload.text.strip():
        raise HTTPException(status_code=400, detail="Input text is empty.")
    doc = extract_from_text(payload.text, name="Web Input")
    models_t = tuple(m for m in payload.models if m in MODEL_REGISTRY)
    ens = _get_ensemble(models_t) if (payload.use_neural and models_t) else None
    aud = _get_auditor() if payload.use_perplexity else None
    report = analyze_document(
        doc,
        models=models_t,
        use_neural=payload.use_neural,
        use_perplexity=payload.use_perplexity,
        ensemble=ens,
        auditor=aud,
    )
    return report.to_dict()


@app.post("/api/scan-file")
async def api_scan_file(
    file: UploadFile = File(...),
    use_neural: bool = Form(True),
    use_perplexity: bool = Form(False),
) -> dict:
    suffix = Path(file.filename or "upload.txt").suffix.lower()
    raw_bytes = await file.read()
    if suffix == ".pdf":
        import fitz

        pdf_doc = fitz.open(stream=raw_bytes, filetype="pdf")
        raw_pages = [p.get_text("text") for p in pdf_doc]
        raw_text = "\n\n".join(raw_pages)
        sections = [
            (f"Page {i}", normalize_extracted_text(p))
            for i, p in enumerate(raw_pages, 1)
            if len(p.split()) >= 10
        ]
        from ..extractors import ExtractedDocument

        doc = ExtractedDocument(
            source_name=file.filename or "upload.pdf",
            raw_text=raw_text,
            clean_text=normalize_extracted_text(raw_text),
            sections=sections,
            hygiene_warnings=inspect_unicode_hygiene(raw_text),
            page_count=len(pdf_doc),
        )
    elif suffix == ".docx":
        import io
        import docx
        from ..extractors import ExtractedDocument

        d = docx.Document(io.BytesIO(raw_bytes))
        raw_text = "\n\n".join(p.text.strip() for p in d.paragraphs if p.text.strip())
        clean = normalize_extracted_text(raw_text)
        doc = ExtractedDocument(
            source_name=file.filename or "upload.docx",
            raw_text=raw_text,
            clean_text=clean,
            sections=split_paragraphs(clean),
            hygiene_warnings=inspect_unicode_hygiene(raw_text),
        )
    else:
        raw_text = raw_bytes.decode("utf-8", errors="replace")
        doc = extract_from_text(raw_text, name=file.filename or "upload.txt")

    models_t = ("fakespot", "academic_det")
    ens = _get_ensemble(models_t) if use_neural else None
    aud = _get_auditor() if use_perplexity else None
    report = analyze_document(
        doc,
        models=models_t,
        use_neural=use_neural,
        use_perplexity=use_perplexity,
        ensemble=ens,
        auditor=aud,
    )
    return report.to_dict()


@app.post("/api/humanize")
def api_humanize(payload: HumanizePayload) -> dict:
    if not payload.text.strip():
        raise HTTPException(status_code=400, detail="Input text is empty.")
    ens = _get_ensemble(("fakespot", "academic_det")) if payload.rescore_neural else None
    before = analyze_document(
        extract_from_text(payload.text),
        use_neural=payload.rescore_neural,
        use_perplexity=False,
        score_sentences=False,
        ensemble=ens,
    )
    res = humanize_text(
        payload.text,
        add_contractions=payload.add_contractions,
        soften_em_dashes=payload.soften_em_dashes,
    )
    after = analyze_document(
        extract_from_text(res.humanized_text),
        use_neural=payload.rescore_neural,
        use_perplexity=False,
        score_sentences=False,
        ensemble=ens,
    )
    return {
        "humanized_text": res.humanized_text,
        "changes_applied": res.changes_applied,
        "before_score": before.overall_ai_score,
        "after_score": after.overall_ai_score,
        "after_report": after.to_dict(),
    }
