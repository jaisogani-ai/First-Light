"""Real keyword search over Mission Files — term-frequency scoring, not embedding-based
semantic search. Labeled honestly as keyword search throughout the API and UI: no
embeddings provider is configured in this deployment (no Voyage/OpenAI key), and claiming
'semantic search' without one would be exactly the kind of fabrication this platform is
built to avoid. Every result traces to and cites a real document/section row.

Stopwords are filtered and matches are exact-word (not substring) — without both, a query
like 'What is the capital of France?' would score hits on 'the'/'is'/'of' inside unrelated
documents (e.g. 'the deterministic verifier'), producing false 'evidence found' results
that would defeat backend/documents/grounding.py's whole purpose: refusing to answer when
nothing real backs the question. This was caught by live-testing the Knowledge Agent, not
guessed at in advance."""

import re

_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "can", "did", "do", "does", "for", "from",
    "had", "has", "have", "how", "i", "if", "in", "into", "is", "it", "its", "of", "on", "or",
    "that", "the", "this", "to", "was", "we", "were", "what", "when", "where", "which", "who",
    "why", "will", "with", "would", "you", "your",
}


def _tokenize(query: str) -> list[str]:
    words = re.findall(r"\w+", query.lower())
    return [w for w in words if w not in _STOPWORDS]


def _count_word(lower_text: str, term: str) -> int:
    return len(re.findall(rf"\b{re.escape(term)}\b", lower_text))


def _snippet(text: str, terms: list[str], context_chars: int = 120) -> str:
    lower = text.lower()
    positions = [lower.find(t) for t in terms]
    positions = [p for p in positions if p != -1]
    first_pos = min(positions) if positions else -1
    if first_pos == -1:
        return text[:context_chars]
    start = max(0, first_pos - context_chars // 2)
    end = min(len(text), first_pos + context_chars // 2)
    prefix, suffix = ("…" if start > 0 else ""), ("…" if end < len(text) else "")
    return f"{prefix}{text[start:end].strip()}{suffix}"


def search_documents(documents: list[dict], query: str, limit: int = 10) -> list[dict]:
    """documents: rows with at least id, filename, doc_type, extracted_text. Returns
    results ranked by real term-frequency score, highest first; documents with zero
    matches are excluded rather than padded in with a fake low score."""
    terms = _tokenize(query)
    if not terms:
        return []

    scored = []
    for doc in documents:
        text = doc.get("extracted_text")
        if not text:
            continue
        lower = text.lower()
        score = sum(_count_word(lower, t) for t in terms)
        if score > 0:
            scored.append({
                "document_id": doc["id"], "filename": doc["filename"], "doc_type": doc["doc_type"],
                "score": score, "snippet": _snippet(text, terms),
            })

    scored.sort(key=lambda r: r["score"], reverse=True)
    return scored[:limit]


def search_sections(sections: list[dict], query: str, limit: int = 10, section_type: str | None = None) -> list[dict]:
    """Section-level search — the corpus backend/documents/grounding.py uses. Each result
    reports document, page, section (type + a short label), and a real confidence score
    (term hits normalized by section length, capped at 1.0 — not a probability, a bounded
    relevance heuristic). sections: rows with document_id, filename, section_type,
    page_number, content_text, order_index."""
    terms = _tokenize(query)
    if not terms:
        return []

    scored = []
    for sec in sections:
        if section_type and sec["section_type"] != section_type:
            continue
        text = sec.get("content_text") or ""
        if not text:
            continue
        lower = text.lower()
        hits = sum(_count_word(lower, t) for t in terms)
        if hits == 0:
            continue
        confidence = min(1.0, hits / max(1, len(text.split())) * 20)  # bounded relevance heuristic, not a probability
        scored.append({
            "document_id": sec["document_id"], "filename": sec["filename"], "section_type": sec["section_type"],
            "page_number": sec.get("page_number"), "confidence": round(confidence, 3),
            "score": hits, "snippet": _snippet(text, terms),
        })

    scored.sort(key=lambda r: r["score"], reverse=True)
    return scored[:limit]
