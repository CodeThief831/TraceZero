"""Document extraction and PDF/text Unicode hygiene inspection."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

INVISIBLE_ARTIFACTS = {
    "\u00a0": "non-breaking space (\\xa0)",
    "\u2011": "non-breaking hyphen (\\u2011)",
    "\u200b": "zero-width space (\\u200b)",
    "\u200c": "zero-width non-joiner (\\u200c)",
    "\u200d": "zero-width joiner (\\u200d)",
    "\ufeff": "BOM / zero-width no-break space (\\ufeff)",
}


@dataclass
class ExtractedDocument:
    """Normalized text and section breakdown extracted from a file or raw input."""

    source_name: str
    raw_text: str
    clean_text: str
    sections: list[tuple[str, str]] = field(default_factory=list)
    hygiene_warnings: list[str] = field(default_factory=list)
    page_count: int = 1


def inspect_unicode_hygiene(text: str) -> list[str]:
    """Detect non-standard whitespace/invisible characters that hurt NLP/AI scanners."""
    warnings: list[str] = []
    for ch, label in INVISIBLE_ARTIFACTS.items():
        count = text.count(ch)
        if count:
            warnings.append(f"Found {count}x {label}")
    return warnings


def normalize_extracted_text(text: str) -> str:
    """Replace non-standard PDF/editor whitespace and hyphens with clean ASCII."""
    cleaned = (
        text.replace("\u00a0", " ")
        .replace("\u2011", "-")
        .replace("\u200b", "")
        .replace("\u200c", "")
        .replace("\u200d", "")
        .replace("\ufeff", "")
    )
    cleaned = re.sub(r"[ \t]+\n", "\n", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def split_paragraphs(text: str, min_words: int = 6) -> list[tuple[str, str]]:
    """Split raw prose into labeled paragraph blocks suitable for section scanning."""
    blocks = [b.strip() for b in re.split(r"\n\s*\n", text) if b.strip()]
    if len(blocks) <= 1 and len(text.split()) > 120:
        blocks = [b.strip() for b in text.splitlines() if len(b.strip().split()) >= min_words]
    results: list[tuple[str, str]] = []
    for idx, blk in enumerate(blocks, 1):
        if len(blk.split()) >= min_words:
            results.append((f"Paragraph {idx}", blk))
    if not results and text.strip():
        results.append(("Document", text.strip()))
    return results


def extract_from_file(path: str | Path) -> ExtractedDocument:
    """Extract text and sections from .pdf, .docx, .txt, or .md files."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"File not found: {p}")

    suffix = p.suffix.lower()
    if suffix == ".pdf":
        import fitz

        doc = fitz.open(str(p))
        raw_pages: list[str] = []
        sections: list[tuple[str, str]] = []
        for idx, page in enumerate(doc, 1):
            raw_p = page.get_text("text")
            raw_pages.append(raw_p)
            clean_p = normalize_extracted_text(raw_p)
            if len(clean_p.split()) >= 10:
                sections.append((f"Page {idx}", clean_p))
        raw_text = "\n\n".join(raw_pages)
        return ExtractedDocument(
            source_name=p.name,
            raw_text=raw_text,
            clean_text=normalize_extracted_text(raw_text),
            sections=sections,
            hygiene_warnings=inspect_unicode_hygiene(raw_text),
            page_count=len(doc),
        )

    if suffix == ".docx":
        import docx

        d = docx.Document(str(p))
        parts = [para.text.strip() for para in d.paragraphs if para.text.strip()]
        for table in d.tables:
            for row in table.rows:
                row_txt = " | ".join(cell.text.strip() for cell in row.cells if cell.text.strip())
                if row_txt:
                    parts.append(row_txt)
        raw_text = "\n\n".join(parts)
        clean = normalize_extracted_text(raw_text)
        return ExtractedDocument(
            source_name=p.name,
            raw_text=raw_text,
            clean_text=clean,
            sections=split_paragraphs(clean),
            hygiene_warnings=inspect_unicode_hygiene(raw_text),
        )

    raw_text = p.read_text(encoding="utf-8", errors="replace")
    clean = normalize_extracted_text(raw_text)
    return ExtractedDocument(
        source_name=p.name,
        raw_text=raw_text,
        clean_text=clean,
        sections=split_paragraphs(clean),
        hygiene_warnings=inspect_unicode_hygiene(raw_text),
    )


def extract_from_text(text: str, name: str = "inline_input") -> ExtractedDocument:
    """Wrap raw inline text into an ExtractedDocument."""
    clean = normalize_extracted_text(text)
    return ExtractedDocument(
        source_name=name,
        raw_text=text,
        clean_text=clean,
        sections=split_paragraphs(clean),
        hygiene_warnings=inspect_unicode_hygiene(text),
    )
