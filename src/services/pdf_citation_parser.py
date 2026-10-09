"""Conservative, offline reference extraction from PDFs with embedded text.

Supported boundaries: a standalone References/Bibliography heading followed by
numbered entries or author (year) entries. Unsupported layouts yield no entries;
metadata without a recognized pattern remains unknown rather than invented.
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from src.database.models import CitationModel

_HEADING = re.compile(
    r"^(?:\d+[.\s]+)?(?:references|bibliography|参考文献)\s*[:：]?\s*$", re.I
)
_STOP = re.compile(
    r"^(?:appendix(?:\s+[A-Z0-9])?|appendices|acknowledg(?:e)?ments|supplementary material)\s*[:：]?\s*$",
    re.I,
)
_NUMBERED = re.compile(r"^(?:\[\d+\]|\d+[.)])\s+(.+)$")
_AUTHOR_YEAR = re.compile(r"^(.+?)\s*\((\d{4})[a-z]?\)\s*\.?\s+(.+)$")
_DOI = re.compile(r"\b10\.\d{4,9}/[^\s<>]+", re.I)


def extract_pdf_references(file_path: str, document_id: int) -> list[CitationModel]:
    """Read actual PDF bytes before constructing any citation records."""
    import pymupdf

    path = Path(file_path)
    if not path.is_file():
        raise ValueError(f"PDF file not found: {file_path}")
    try:
        with pymupdf.open(path) as pdf:
            if not pdf.is_pdf or pdf.needs_pass:
                raise ValueError("Citation extraction requires an unlocked PDF")
            lines = [
                line.strip()
                for page in pdf
                for line in page.get_text("text", sort=True).splitlines()
            ]
    except (pymupdf.FileDataError, pymupdf.EmptyFileError) as exc:
        raise ValueError(f"Cannot read PDF: {file_path}") from exc

    entries: list[str] = []
    current: list[str] = []
    in_references = False
    style: str | None = None
    for line in lines:
        if _HEADING.fullmatch(line):
            in_references = True
            continue
        if not in_references:
            continue
        if _STOP.fullmatch(line):
            break
        if not line or line.isdigit():  # blank lines and bare page numbers
            continue
        numbered = _NUMBERED.match(line)
        author_year = _AUTHOR_YEAR.match(line)
        starts_entry = (numbered is not None and style in (None, "numbered")) or (
            author_year is not None and style in (None, "author_year")
        )
        if starts_entry:
            if current:
                entries.append(" ".join(current))
            style = "numbered" if numbered else "author_year"
            current = [line]
        elif current:
            current.append(line)
    if current:
        entries.append(" ".join(current))

    citations = []
    for raw_text in dict.fromkeys(entries):
        content = _NUMBERED.sub(r"\1", raw_text, count=1)
        match = _AUTHOR_YEAR.match(content)
        authors = title = None
        year = None
        if match:
            candidate_year = int(match[2])
            if 1000 <= candidate_year <= datetime.now().year + 1:
                authors, year = match[1].strip(), candidate_year
                title = match[3].split(". ", 1)[0].rstrip(".") or None
        doi = _DOI.search(content)
        citations.append(
            CitationModel(
                document_id=document_id,
                raw_text=raw_text,
                authors=authors,
                title=title,
                publication_year=year,
                doi=doi[0].rstrip(".,;)") if doi else None,
                confidence_score=None,  # no calibrated confidence model
            )
        )
    return citations
