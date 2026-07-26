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
        from sentence_transformers import SentenceTransformer
        self._model = SentenceTransformer(self.model_name)
        self._dimension = self._model.get_sentence_embedding_dimension()

    async def embed(self, texts: list[str]) -> np.ndarray:
        self._load()
        return self._model.encode(texts, normalize_embeddings=True, show_progress_bar=False)

    async def embed_query(self, text: str) -> np.ndarray:
        self._load()
        return self._model.encode([text], normalize_embeddings=True, show_progress_bar=False)[0]

    @property
    def dimension(self) -> int:
        self._load()
        return self._dimension
