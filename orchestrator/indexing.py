import logging

from ingestion.docling_ingestor import ingest_document
from app.config import settings
from rag.chunker import chunk_structured_text
from rag.vector_store import FaissVectorStore

logger = logging.getLogger(__name__)


def ingest_and_index(file_path: str) -> dict:
    logger.info("Indexing started. file_path=%s", file_path)
    structured = ingest_document(file_path=file_path)
    chunks = chunk_structured_text(
        structured,
        chunk_size=settings.chunk_size_tokens,
        overlap=settings.chunk_overlap_tokens,
    )
    if not chunks:
        logger.warning("No chunks produced from document. file_path=%s", file_path)
        return {
            "file_path": file_path,
            "sections": len(structured),
            "chunks": 0,
            "index_created": False,
        }
    store = FaissVectorStore()
    if store.index_exists():
        store.add_to_index(chunks)
        index_created = False
    else:
        store.create_index(chunks)
        index_created = True
    result = {
        "file_path": file_path,
        "sections": len(structured),
        "chunks": len(chunks),
        "index_created": index_created,
    }
    logger.info(
        "Indexing finished. file_path=%s sections=%s chunks=%s index_created=%s",
        result["file_path"],
        result["sections"],
        result["chunks"],
        result["index_created"],
    )
    return result
