import re


def _classify_content(text: str) -> str:
    lowered = text.lower()
    if "definition" in lowered:
        return "definition"
    if "example" in lowered or "for instance" in lowered:
        return "example"
    if "theorem" in lowered:
        return "theorem"
    if "exercise" in lowered or "question" in lowered:
        return "exercise"
    return "explanation"


def _normalize_structure_items(structured_items: list[dict]) -> list[dict]:
    normalized: list[dict] = []
    for item in structured_items:
        text = str(item.get("text", "")).strip()
        if not text:
            continue
        section = str(item.get("section", "general")).strip() or "general"
        source = str(item.get("source", "unknown")).strip() or "unknown"
        normalized.append({"text": text, "section": section, "source": source})
    return normalized


def _split_tokens(text: str) -> list[str]:
    return re.findall(r"\S+", text)


def chunk_structured_text(
    structured_items: list[dict], chunk_size: int = 512, overlap: int = 50
) -> list[dict]:
    """
    Two-stage chunking:
    1) structure-aware sections are provided by ingestion (header grouped)
    2) token-window splitting per section (512/50 by default)
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be > 0")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be >= 0 and < chunk_size")

    sections = _normalize_structure_items(structured_items)
    output: list[dict] = []
    chunk_id = 1
    step = chunk_size - overlap

    for item in sections:
        tokens = _split_tokens(item["text"])
        if not tokens:
            continue
        for start in range(0, len(tokens), step):
            window = tokens[start : start + chunk_size]
            if not window:
                continue
            snippet = " ".join(window).strip()
            if not snippet:
                continue
            output.append(
                {
                    "chunk": snippet,
                    "section": item["section"],
                    "source": item["source"],
                    "chunk_id": chunk_id,
                    "content_type": _classify_content(snippet),
                }
            )
            chunk_id += 1
    return output
