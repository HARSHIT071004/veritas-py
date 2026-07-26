from typing import Optional
from app.mcp.tools.base import Tool, ToolSpec


class RetrievalTool(Tool):
    spec = ToolSpec(
        name="retrieve_evidence",
        description="Search trusted knowledge base for evidence relevant to a claim. Returns top matching documents.",
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Claim or question to find evidence for"},
                "top_k": {"type": "integer", "description": "Number of results", "default": 5}
            },
            "required": ["query"]
        }
    )

    def __init__(self, collection=None, embedding_fn=None):
        self._collection = collection
        self._embedding_fn = embedding_fn

    async def execute(self, query: str, top_k: int = 5) -> dict:
        if not self._collection or not self._embedding_fn:
            return {"results": [], "total": 0}
        try:
            embedding = await self._embedding_fn(query)
            results = self._collection.query(
                query_embeddings=[embedding],
                n_results=top_k
            )
            docs = []
            for i in range(len(results.get("ids", [[]])[0])):
                doc = {
                    "id": results["ids"][0][i],
                    "content": results["documents"][0][i],
                    "metadata": results["metadatas"][0][i] if results.get("metadatas") else {},
                    "distance": results["distances"][0][i] if results.get("distances") else 0
                }
                docs.append(doc)
            return {"results": docs, "total": len(docs)}
        except Exception as e:
            return {"results": [], "total": 0, "error": str(e)}
