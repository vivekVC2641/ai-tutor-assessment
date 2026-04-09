import logging

from app.config import settings
from rag.vector_store import FaissVectorStore

logger = logging.getLogger(__name__)

INDEX_MISSING_ERROR = "Knowledge index not found. Run /ingest first."


def _cohere_rerank(query: str, results: list[dict], k: int) -> list[dict]:
    if not settings.rerank_enabled or not settings.cohere_api_key.strip() or not results:
        return results[:k]

    try:
        import cohere

        client = cohere.ClientV2(api_key=settings.cohere_api_key.strip())
        documents = [item.get("chunk", "") for item in results]
        response = client.rerank(
            model=settings.cohere_rerank_model,
            query=query,
            documents=documents,
            top_n=min(k, len(documents)),
        )
        reranked: list[dict] = []
        for item in response.results:
            idx = item.index
            if idx < 0 or idx >= len(results):
                continue
            base = dict(results[idx])
            base["rerank_score"] = float(item.relevance_score)
            reranked.append(base)
        if reranked:
            logger.info("Cohere rerank applied on %s chunks", len(reranked))
            return reranked
    except Exception as exc:
        logger.warning("Cohere rerank failed, using vector order. reason=%s", exc)
    return results[:k]


def retrieve_top_chunks(query: str, k: int = 5) -> list[dict]:
    store = FaissVectorStore()
    if not store.index_exists():
        raise FileNotFoundError(INDEX_MISSING_ERROR)
    candidate_k = max(k, 8) if settings.rerank_enabled else k
    results = store.similarity_search(query=query, k=candidate_k)
    results = _cohere_rerank(query=query, results=results, k=k)
    for r in results:
        logger.info(
            "Retrieved chunk_id=%s section=%s source=%s",
            r.get("chunk_id"),
            r.get("section"),
            r.get("source"),
        )
    return results
