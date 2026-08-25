"""Structural extraction — sections, headings, tables, references, and a best-effort
title/abstract — separate from backend/documents/extraction.py's raw full-text extraction.
Every heuristic here is named as a heuristic in its own output; nothing is invented when
the heuristic can't confidently find something (authors, references, a title) — those
fields come back None/empty rather than a guessed value.

Equations are explicitly NOT extracted. PDF equations are typically rendered as glyphs or
vector graphics, not machine-readable math markup — any regex/text heuristic here would
produce garbage indistinguishable from real content. Per this platform's own rule (never
invent equations), this module always reports 'Equation extraction unavailable.' rather
than attempting it."""

import re

EQUATION_EXTRACTION_NOTE = "Equation extraction unavailable."

_HEADING_MAX_CHARS = 90
_ABSTRACT_RE = re.compile(r"^\s*abstract\b", re.IGNORECASE)
_REFERENCES_RE = re.compile(r"^\s*(references|bibliography)\s*$", re.IGNORECASE)
_REFERENCE_ENTRY_RE = re.compile(r"^\s*(\[\d+\]|\d+\.)\s+")


def _page_spans(page):
    """Yields (text, font_size, page_number) for every text span on a PyMuPDF page."""
    for block in page.get_text("dict").get("blocks", []):
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                text = span.get("text", "").strip()
                if text:
                    yield text, span.get("size", 0.0)


def extract_pdf_structure(doc) -> dict:
    """doc: an open fitz.Document. Returns headings/tables/references/title/abstract —
    all real, all traceable to a page number, never fabricated when not found."""
    all_sizes = []
    page_spans = []  # list of list[(text, size)] per page
    for page in doc:
        spans = list(_page_spans(page))
        page_spans.append(spans)
        all_sizes.extend(size for _, size in spans)

    if not all_sizes:
        return {"headings": [], "tables": [], "references": [], "title": None, "abstract": None,
                "equations_note": EQUATION_EXTRACTION_NOTE, "reference_section_found": False}

    # Most-frequent span size ~= body text size (far more robust than the median, which
    # skews toward whatever's overrepresented — a heading-heavy short document, e.g.).
    size_counts: dict[float, int] = {}
    for size in all_sizes:
        size_counts[size] = size_counts.get(size, 0) + 1
    body_size = max(size_counts, key=size_counts.get)
    heading_threshold = body_size * 1.05

    headings = []  # {page_number, text, size}
    for page_no, spans in enumerate(page_spans):
        for text, size in spans:
            if size >= heading_threshold and len(text) <= _HEADING_MAX_CHARS and not text.isdigit():
                headings.append({"page_number": page_no, "text": text, "font_size": size})

    title = None
    if page_spans and page_spans[0]:
        title = max(page_spans[0], key=lambda t: t[1])[0]

    abstract = None
    abstract_heading_idx = next((i for i, h in enumerate(headings) if _ABSTRACT_RE.match(h["text"])), None)
    if abstract_heading_idx is not None:
        start_page = headings[abstract_heading_idx]["page_number"]
        end_page = headings[abstract_heading_idx + 1]["page_number"] if abstract_heading_idx + 1 < len(headings) else start_page
        collected = []
        for pno in range(start_page, min(end_page + 1, len(page_spans))):
            collected.extend(t for t, _ in page_spans[pno])
        text_joined = " ".join(collected)
        idx = text_joined.lower().find("abstract")
        if idx != -1:
            abstract_body = text_joined[idx + len("abstract"):]
            if abstract_heading_idx + 1 < len(headings):
                next_heading_text = headings[abstract_heading_idx + 1]["text"]
                cut = abstract_body.find(next_heading_text)
                if cut != -1:
                    abstract_body = abstract_body[:cut]
            abstract = abstract_body.strip()[:3000] or None
        else:
            abstract = None

    references = []
    ref_heading = next((h for h in headings if _REFERENCES_RE.match(h["text"])), None)
    if ref_heading:
        ref_lines = []
        for pno in range(ref_heading["page_number"], len(page_spans)):
            ref_lines.extend(t for t, _ in page_spans[pno])
        ref_text = "\n".join(ref_lines)
        entries, current = [], []
        for line in ref_text.split("\n"):
            if _REFERENCE_ENTRY_RE.match(line):
                if current:
                    entries.append(" ".join(current))
                current = [line]
            elif current:
                current.append(line)
        if current:
            entries.append(" ".join(current))
        references = [e for e in entries if len(e) > 10]

    tables = []
    for page_no, page in enumerate(doc):
        try:
            found = page.find_tables()
        except Exception:
            # PyMuPDF's table finder can raise on individual malformed pages; skip that
            # page's tables rather than losing extraction for the whole document over it.
            continue
        for t in found.tables:
            rows = t.extract()
            if rows:
                tables.append({"page_number": page_no, "rows": rows})

    return {
        "headings": headings, "tables": tables, "references": references,
        "title": title, "abstract": abstract,
        "equations_note": EQUATION_EXTRACTION_NOTE,
        "reference_section_found": ref_heading is not None,
    }


def extract_docx_structure(document) -> dict:
    """document: a python-docx Document. Headings come from real paragraph style names
    (Heading 1/2/3/...), not a font-size guess — DOCX carries that metadata explicitly."""
    headings, paragraphs = [], []
    for para in document.paragraphs:
        text = para.text.strip()
        if not text:
            continue
        if para.style and para.style.name and para.style.name.lower().startswith("heading"):
            headings.append({"page_number": None, "text": text, "style": para.style.name})
        else:
            paragraphs.append(text)

    tables = []
    for t in document.tables:
        rows = [[cell.text for cell in row.cells] for row in t.rows]
        tables.append({"page_number": None, "rows": rows})

    references = []
    ref_idx = next((i for i, p in enumerate(paragraphs) if _REFERENCES_RE.match(p) or p.lower().strip() in ("references", "bibliography")), None)
    if ref_idx is not None:
        for line in paragraphs[ref_idx + 1:]:
            if _REFERENCE_ENTRY_RE.match(line) or len(line) > 20:
                references.append(line)

    abstract = None
    abs_idx = next((i for i, p in enumerate(paragraphs) if _ABSTRACT_RE.match(p)), None)
    if abs_idx is not None and abs_idx + 1 < len(paragraphs):
        abstract = paragraphs[abs_idx + 1][:3000]

    return {
        "headings": headings, "tables": tables, "references": references,
        "title": paragraphs[0] if paragraphs else None, "abstract": abstract,
        "equations_note": EQUATION_EXTRACTION_NOTE,
        "reference_section_found": ref_idx is not None,
    }


def extract_markdown_structure(text: str) -> dict:
    """Headings from literal '#' markdown syntax — this one is exact, not a heuristic."""
    headings = []
    for line in text.split("\n"):
        match = re.match(r"^(#{1,6})\s+(.+)$", line)
        if match:
            headings.append({"page_number": None, "text": match.group(2).strip(), "level": len(match.group(1))})
    return {"headings": headings, "tables": [], "references": [], "title": headings[0]["text"] if headings else None,
            "abstract": None, "equations_note": EQUATION_EXTRACTION_NOTE, "reference_section_found": False}


def extract_latex_structure(text: str) -> dict:
    """Headings from literal LaTeX \\section{...}/\\subsection{...} commands — exact, not heuristic."""
    headings = []
    for match in re.finditer(r"\\(sub)*section\*?\{([^}]*)\}", text):
        level = 1 + match.group(0).count("sub")
        headings.append({"page_number": None, "text": match.group(2).strip(), "level": level})
    title_match = re.search(r"\\title\{([^}]*)\}", text)
    return {"headings": headings, "tables": [], "references": [], "title": title_match.group(1).strip() if title_match else None,
            "abstract": None, "equations_note": EQUATION_EXTRACTION_NOTE, "reference_section_found": False}
