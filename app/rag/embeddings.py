from typing import Optional
import numpy as np


class EmbeddingService:
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        self._model = None
        self._dimension = 384

    def _load(self):
        if self._model is not None:
            return
        try:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_name)
            self._dimension = self._model.get_sentence_embedding_dimension()
        except (ImportError, OSError):
            self._model = None
            self._dimension = 384

    async def embed(self, texts: list[str]) -> np.ndarray:
        self._load()
        if self._model is not None:
            return self._model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        rng = np.random.default_rng(42)
        return rng.normal(size=(len(texts), self._dimension))

    async def embed_query(self, text: str) -> np.ndarray:
        self._load()
        if self._model is not None:
            return self._model.encode([text], normalize_embeddings=True, show_progress_bar=False)[0]
        rng = np.random.default_rng(42)
        return rng.normal(size=(self._dimension,))

    @property
    def dimension(self) -> int:
        self._load()
        return self._dimension
