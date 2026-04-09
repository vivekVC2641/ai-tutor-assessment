import json
import logging
from pathlib import Path

import faiss
import numpy as np

from app.config import settings
from app.llm_client import get_embedding_client

logger = logging.getLogger(__name__)

INDEX_FILE = "index.faiss"
META_FILE = "metadata.json"


class FaissVectorStore:
    def __init__(self) -> None:
        self.base_dir = Path(settings.index_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.client, self.embedding_model = get_embedding_client()

    def _embed(self, texts: list[str]) -> np.ndarray:
        resp = self.client.embeddings.create(model=self.embedding_model, input=texts)
        vectors = [item.embedding for item in resp.data]
        return np.array(vectors, dtype=np.float32)

    def create_index(self, chunks: list[dict]) -> None:
        if not chunks:
            raise ValueError("Cannot create index from empty chunks")
        texts = [c["chunk"] for c in chunks]
        embeddings = self._embed(texts)
        dim = embeddings.shape[1]
        index = faiss.IndexFlatL2(dim)
        index.add(embeddings)

        faiss.write_index(index, str(self.base_dir / INDEX_FILE))
        (self.base_dir / META_FILE).write_text(
            json.dumps(chunks, ensure_ascii=True, indent=2), encoding="utf-8"
        )
        logger.info("FAISS index created with %s chunks", len(chunks))

    def add_to_index(self, chunks: list[dict]) -> None:
        """
        Append chunks into an existing index (and metadata.json).

        Note: This uses IndexFlatL2 which supports incremental adds.
        """
        if not chunks:
            raise ValueError("Cannot add empty chunks")
        if not self.index_exists():
            self.create_index(chunks)
            return

        index, metadata = self.load_index()
        texts = [c["chunk"] for c in chunks]
        embeddings = self._embed(texts)

        if embeddings.ndim != 2:
            raise ValueError("Embeddings must be a 2D array")
        if embeddings.shape[1] != index.d:
            raise ValueError(
                f"Embedding dim mismatch. index_dim={index.d} new_dim={embeddings.shape[1]}"
            )

        index.add(embeddings)
        metadata.extend(chunks)

        faiss.write_index(index, str(self.base_dir / INDEX_FILE))
        (self.base_dir / META_FILE).write_text(
            json.dumps(metadata, ensure_ascii=True, indent=2), encoding="utf-8"
        )
        logger.info("FAISS index updated; total chunks=%s (+%s)", len(metadata), len(chunks))

    def load_index(self) -> tuple[faiss.Index, list[dict]]:
        index_path = self.base_dir / INDEX_FILE
        meta_path = self.base_dir / META_FILE
        if not index_path.exists() or not meta_path.exists():
            raise FileNotFoundError("Index or metadata does not exist. Create index first.")
        index = faiss.read_index(str(index_path))
        metadata = json.loads(meta_path.read_text(encoding="utf-8"))
        return index, metadata

    def index_exists(self) -> bool:
        index_path = self.base_dir / INDEX_FILE
        meta_path = self.base_dir / META_FILE
        return index_path.exists() and meta_path.exists()

    def similarity_search(self, query: str, k: int = 3) -> list[dict]:
        index, metadata = self.load_index()
        q_vec = self._embed([query])
        distances, indices = index.search(q_vec, k)
        results: list[dict] = []
        for rank, idx in enumerate(indices[0]):
            if idx < 0 or idx >= len(metadata):
                continue
            item = metadata[idx]
            item["distance"] = float(distances[0][rank])
            results.append(item)
        logger.info("Retrieved %s chunks for query", len(results))
        return results
