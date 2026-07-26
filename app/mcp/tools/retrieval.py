from app.mcp.tools.base import Tool, ToolSpec
from app.rag.engine import RAGEngine


class RetrievalTool(Tool):
    spec = ToolSpec(
        name="retrieve_evidence",
        description="Search trusted knowledge base for evidence relevant to a claim. Returns top matching documents with hybrid search (FAISS + BM25 + cross-encoder re-ranking).",
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Claim or question to find evidence for"},
                "top_k": {"type": "integer", "description": "Number of results", "default": 5}
            },
            "required": ["query"]
        }
    )

    def __init__(self, engine: RAGEngine = None):
        self._engine = engine

    async def execute(self, query: str, top_k: int = 5) -> dict:
        if not self._engine or self._engine.document_count == 0:
            return {"results": [], "total": 0, "method": "none"}
        try:
            results = await self._engine.search(query, top_k=top_k)
            return {"results": results, "total": len(results), "method": "hybrid"}
        except Exception as e:
            return {"results": [], "total": 0, "error": str(e), "method": "none"}
