import json
import pickle
import numpy as np
from pathlib import Path
from typing import Optional

from app.rag.embeddings import EmbeddingService


class RAGEngine:
    def __init__(self, persist_dir: str = "data/rag"):
        self.persist_dir = Path(persist_dir)
        self.persist_dir.mkdir(parents=True, exist_ok=True)

        self._embedder: Optional[EmbeddingService] = None
        self._faiss_index = None
        self._bm25 = None
        self._cross_encoder = None
        self._documents: list[dict] = []
        self._doc_ids: list[str] = []
        self._bm25_corpus: list[str] = []
        self._index_loaded = False

    # ── lazy loading ──────────────────────────────────────────

    def _ensure_embedder(self):
        if self._embedder is None:
            self._embedder = EmbeddingService()

    def _ensure_cross_encoder(self):
        if self._cross_encoder is None:
            from sentence_transformers import CrossEncoder
            self._cross_encoder = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")

    def _ensure_bm25(self):
        if self._bm25 is None and self._bm25_corpus:
            from rank_bm25 import BM25Okapi
            self._bm25 = BM25Okapi([doc.split() for doc in self._bm25_corpus])

    def _ensure_faiss(self):
        if self._faiss_index is None and len(self._documents) > 0:
            import faiss
            self._ensure_embedder()
            dim = self._embedder.dimension
            self._faiss_index = faiss.IndexFlatIP(dim)

    # ── ingestion ─────────────────────────────────────────────

    async def ingest(self, documents: list[dict], chunk_size: int = 512, chunk_overlap: int = 64):
        chunks = []
        for doc in documents:
            content = doc.get("content", "")
            for i in range(0, len(content), chunk_size - chunk_overlap):
                chunk_text = content[i:i + chunk_size]
                if len(chunk_text.strip()) < 20:
                    continue
                chunk_id = f"{doc['id']}_chunk_{i}"
                chunks.append({
                    "id": chunk_id,
                    "content": chunk_text,
                    "metadata": {k: v for k, v in doc.items() if k not in ("content", "id")}
                })

        if not chunks:
            return 0

        self._ensure_embedder()
        texts = [c["content"] for c in chunks]
        embeddings = await self._embedder.embed(texts)

        import faiss
        dim = embeddings.shape[1]
        index = faiss.IndexFlatIP(dim)
        index.add(embeddings.astype(np.float32))

        self._faiss_index = index
        self._documents = chunks
        self._doc_ids = [c["id"] for c in chunks]
        self._bm25_corpus = texts
        self._bm25 = None
        self._index_loaded = True

        self._persist()
        return len(chunks)

    # ── retrieval ─────────────────────────────────────────────

    async def search(self, query: str, top_k: int = 5) -> list[dict]:
        if not self._index_loaded or len(self._documents) == 0:
            return []

        self._ensure_embedder()
        self._ensure_faiss()
        self._ensure_bm25()

        query_vec = (await self._embedder.embed_query(query)).reshape(1, -1).astype(np.float32)
        faiss_scores, faiss_indices = self._faiss_index.search(query_vec, min(top_k * 4, len(self._documents)))
        faiss_results = {int(faiss_indices[0][i]): float(faiss_scores[0][i]) for i in range(len(faiss_indices[0])) if faiss_indices[0][i] != -1}

        bm25_scores = self._bm25.get_scores(query.split())
        bm25_ranks = np.argsort(bm25_scores)[::-1][:top_k * 4]
        bm25_results = {int(idx): float(bm25_scores[idx]) for idx in bm25_ranks if bm25_scores[idx] > 0}

        all_indices = set(faiss_results.keys()) | set(bm25_results.keys())
        if not all_indices:
            return []

        rrf_scores = {}
        for idx in all_indices:
            faiss_rank = sorted(faiss_results.keys(), key=lambda i: faiss_results[i], reverse=True).index(idx) + 1 if idx in faiss_results else top_k * 4
            bm25_rank = sorted(bm25_results.keys(), key=lambda i: bm25_results[i], reverse=True).index(idx) + 1 if idx in bm25_results else top_k * 4
            rrf_scores[idx] = (1 / (60 + faiss_rank)) + (1 / (60 + bm25_rank))

        rerank_candidates = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)[:top_k * 2]

        self._ensure_cross_encoder()
        pairs = [(query, self._documents[idx]["content"]) for idx, _ in rerank_candidates]
        ce_scores = self._cross_encoder.predict(pairs)

        results = []
        for (idx, rrf_score), ce_score in zip(rerank_candidates, ce_scores):
            doc = self._documents[int(idx)]
            results.append({
                "id": doc["id"],
                "content": doc["content"][:2000],
                "metadata": doc.get("metadata", {}),
                "score": float(ce_score),
                "rrf_score": rrf_score
            })

        results.sort(key=lambda r: r["score"], reverse=True)
        return results[:top_k]

    # ── persistence ───────────────────────────────────────────

    def _persist(self):
        if not self._index_loaded:
            return
        import faiss
        faiss.write_index(self._faiss_index, str(self.persist_dir / "faiss.index"))
        with open(self.persist_dir / "documents.pkl", "wb") as f:
            pickle.dump({
                "documents": self._documents,
                "doc_ids": self._doc_ids,
                "bm25_corpus": self._bm25_corpus
            }, f)

    def load(self):
        faiss_path = self.persist_dir / "faiss.index"
        docs_path = self.persist_dir / "documents.pkl"
        if not faiss_path.exists() or not docs_path.exists():
            return False
        import faiss
        self._faiss_index = faiss.read_index(str(faiss_path))
        with open(docs_path, "rb") as f:
            data = pickle.load(f)
            self._documents = data["documents"]
            self._doc_ids = data["doc_ids"]
            self._bm25_corpus = data["bm25_corpus"]
        self._index_loaded = True
        return True

    @property
    def document_count(self) -> int:
        return len(self._documents)
