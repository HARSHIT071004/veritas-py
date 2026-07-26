from typing import AsyncIterator
from app.rag.engine import RAGEngine


class IngestionPipeline:
    def __init__(self, engine: RAGEngine):
        self._engine = engine

    async def ingest_stream(self, documents: AsyncIterator[list[dict]]) -> dict:
        total = 0
        batch_size = 50

        async for batch in documents:
            count = await self._engine.ingest(batch)
            total += count

        return {"ingested": total}

    async def ingest_batch(self, documents: list[dict]) -> dict:
        count = await self._engine.ingest(documents)
        return {"ingested": count}

    @staticmethod
    def chunk_text(text: str, chunk_size: int = 512, overlap: int = 64) -> list[str]:
        chunks = []
        for i in range(0, len(text), chunk_size - overlap):
            chunk = text[i:i + chunk_size]
            if len(chunk.strip()) >= 20:
                chunks.append(chunk)
        return chunks
