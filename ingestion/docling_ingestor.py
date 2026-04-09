import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)


def clean_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _split_markdown_by_headers(markdown: str, source: str) -> list[dict]:
    """
    Split markdown by headings to preserve document structure.

    Returns list of: {"text": "...", "section": "...", "source": "..."}
    """
    lines = markdown.splitlines()
    items: list[dict] = []
    current_section = "general"
    buffer: list[str] = []

    def flush() -> None:
        if not buffer:
            return
        text = clean_text("\n".join(buffer))
        if text:
            items.append({"text": text, "section": current_section, "source": source})
        buffer.clear()

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            buffer.append("")
            continue

        header_match = re.match(r"^(#{1,6})\s+(.+)$", line)
        if header_match:
            flush()
            current_section = clean_text(header_match.group(2))
            continue

        buffer.append(raw_line)

    flush()
    return items


def ingest_document(file_path: str) -> list[dict]:
    """
    Load PDF/DOCX via docling when available.
    Returns list of: {"text": "...", "section": "...", "source": "..."}
    """
    source = Path(file_path).name
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    try:
        from docling.document_converter import DocumentConverter  # type: ignore

        converter = DocumentConverter()
        result = converter.convert(str(path))
        markdown = result.document.export_to_markdown()
        structured_sections = _split_markdown_by_headers(markdown=markdown, source=source)
        if structured_sections:
            logger.info("Ingested %s structured sections using docling from %s", len(structured_sections), source)
            return structured_sections

        paragraphs = [p for p in markdown.split("\n\n") if p.strip()]
        fallback_sections = [
            {"text": clean_text(p), "section": "general", "source": source}
            for p in paragraphs
            if clean_text(p)
        ]
        logger.info("Ingested %s fallback sections using docling from %s", len(fallback_sections), source)
        return fallback_sections
    except Exception as exc:
        logger.exception("Docling ingestion failed for %s: %s", source, exc)
        # Graceful fallback for plain text-like content
        raw = path.read_text(encoding="utf-8", errors="ignore")
        fallback = [{"text": clean_text(raw), "section": "full_text", "source": source}]
        logger.info("Fallback ingestion completed for %s", source)
        return fallback
