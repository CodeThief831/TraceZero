"""Deterministic, semantics-preserving humanization and text-hygiene passes."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..extractors import normalize_extracted_text

# Case-preserving phrase replacements for common AI filler & stiff transitions
PHRASE_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    (r"\bit is important to note that\b", "notably,"),
    (r"\bit is essential to\b", "you need to"),
    (r"\bit is crucial to\b", "we have to"),
    (r"\bin order to\b", "to"),
    (r"\bin today's fast-paced world,?\b", "today,"),
    (r"\bin conclusion,?\b", "overall,"),
    (r"\bfurthermore,?\b", "also,"),
    (r"\bmoreover,?\b", "beyond that,"),
    (r"\badditionally,?\b", "on top of that,"),
    (r"\bsubsequently,?\b", "later,"),
    (r"\bconsequently,?\b", "as a result,"),
    (r"\bdelve into\b", "dig into"),
    (r"\bdelves into\b", "digs into"),
    (r"\butilize\b", "use"),
    (r"\butilizes\b", "uses"),
    (r"\butilizing\b", "using"),
    (r"\bleverage\b", "use"),
    (r"\bleverages\b", "uses"),
    (r"\bleveraging\b", "using"),
    (r"\bfacilitate\b", "support"),
    (r"\bfacilitates\b", "supports"),
    (r"\bbolster\b", "strengthen"),
    (r"\bsafeguard\b", "protect"),
    (r"\bcomprehensive\b", "complete"),
    (r"\brobust\b", "solid"),
    (r"\bcrucial\b", "key"),
    (r"\bvital\b", "key"),
    (r"\bpivotal\b", "central"),
    (r"\bparamount\b", "top priority"),
    (r"\bstreamline\b", "simplify"),
    (r"\bseamlessly\b", "smoothly"),
    (r"\bseamless\b", "smooth"),
    (r"\bholistic\b", "end-to-end"),
    (r"\bactionable\b", "practical"),
    (r"\bproactively\b", "early on"),
    (r"\bproactive\b", "early"),
    (r"\bunderscore\b", "highlight"),
    (r"\bunderscores\b", "highlights"),
    (r"\bfoster\b", "encourage"),
    (r"\bensure that\b", "make sure"),
    (r"\bensure\b", "make sure"),
    (r"\bconfirm whether\b", "check if"),
    (r"\bestablish whether\b", "check if"),
    (r"\bestablish which\b", "find which"),
)

CONTRACTION_PAIRS: tuple[tuple[str, str], ...] = (
    (r"\bdo not\b", "don't"),
    (r"\bdoes not\b", "doesn't"),
    (r"\bdid not\b", "didn't"),
    (r"\bcannot\b", "can't"),
    (r"\bcan not\b", "can't"),
    (r"\bwill not\b", "won't"),
    (r"\bis not\b", "isn't"),
    (r"\bare not\b", "aren't"),
    (r"\bshould not\b", "shouldn't"),
    (r"\bwould not\b", "wouldn't"),
    (r"\bit is\b", "it's"),
    (r"\bthat is\b", "that's"),
    (r"\bthere is\b", "there's"),
)


@dataclass
class HumanizeResult:
    """Result of applying deterministic humanization and hygiene passes."""

    original_text: str
    humanized_text: str
    changes_applied: list[str] = field(default_factory=list)


def _match_case(src: str, repl: str) -> str:
    if src.isupper():
        return repl.upper()
    if src[0].isupper():
        return repl[0].upper() + repl[1:]
    return repl


def humanize_text(
    text: str,
    add_contractions: bool = True,
    soften_em_dashes: bool = True,
) -> HumanizeResult:
    """Apply deterministic hygiene and anti-AI phrasing passes without altering facts."""
    changes: list[str] = []
    out = normalize_extracted_text(text)
    if out != text:
        changes.append("Normalized invisible PDF/editor whitespace and hyphens to clean ASCII.")

    phrase_hits = 0
    for pattern, repl in PHRASE_REPLACEMENTS:
        regex = re.compile(pattern, re.IGNORECASE)
        out, n = regex.subn(lambda m, r=repl: _match_case(m.group(0), r), out)
        phrase_hits += n
    if phrase_hits:
        changes.append(f"Replaced {phrase_hits} stiff/AI-overused phrase(s) with plain phrasing.")

    if soften_em_dashes and "—" in out:
        count = out.count("—")
        out = re.sub(r"\s*—\s*", ", ", out)
        changes.append(f"Replaced {count} em-dash(es) with standard comma pauses.")

    if add_contractions:
        c_hits = 0
        # Apply sparingly (~every second match) so cadence remains natural, not forced
        for pattern, repl in CONTRACTION_PAIRS:
            regex = re.compile(pattern, re.IGNORECASE)
            matches = list(regex.finditer(out))
            if not matches:
                continue
            def _sub_contraction(m, r=repl):
                nonlocal c_hits
                c_hits += 1
                return _match_case(m.group(0), r)

            # Replace up to 2 occurrences per contraction pattern to avoid over-contraction
            out = regex.sub(_sub_contraction, out, count=2)
        if c_hits:
            changes.append(f"Introduced {c_hits} natural contraction(s).")

    # Clean accidental double commas or spaces
    out = re.sub(r",\s*,+", ",", out)
    out = re.sub(r"[ \t]{2,}", " ", out)
    out = re.sub(r" +([,.!?;:])", r"\1", out).strip()

    return HumanizeResult(
        original_text=text,
        humanized_text=out,
        changes_applied=changes,
    )
