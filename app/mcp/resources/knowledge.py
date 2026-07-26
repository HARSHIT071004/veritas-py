import json
from pathlib import Path
from typing import Optional, Any
from app.mcp.resources.base import Resource, ResourceSpec
from app.data.models import KnowledgeDocument


class KnowledgeResource(Resource):
    spec = ResourceSpec(
        uri="knowledge://documents",
        name="Knowledge Base",
        description="Trusted knowledge documents for fact-checking"
    )

    def __init__(self, persist_dir: str = "data/knowledge"):
        self.persist_dir = Path(persist_dir)
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self._documents: dict[str, KnowledgeDocument] = {}
        self._load()

    def _load(self):
        path = self.persist_dir / "documents.json"
        if path.exists():
            with open(path) as f:
                data = json.load(f)
                for d in data:
                    doc = KnowledgeDocument(**d)
                    self._documents[doc.id] = doc

    def _save(self):
        with open(self.persist_dir / "documents.json", "w") as f:
            json.dump([d.__dict__ for d in self._documents.values()], f, indent=2)

    def add_document(self, doc: KnowledgeDocument):
        self._documents[doc.id] = doc
        self._save()

    def add_documents(self, docs: list[KnowledgeDocument]):
        for doc in docs:
            self._documents[doc.id] = doc
        self._save()

    def get_all(self) -> list[KnowledgeDocument]:
        return list(self._documents.values())

    def get_by_tier(self, tier: int) -> list[KnowledgeDocument]:
        return [d for d in self._documents.values() if d.source_tier == tier]

    def get_by_source(self, source: str) -> list[KnowledgeDocument]:
        return [d for d in self._documents.values() if d.source.lower() == source.lower()]

    async def read(self, uri_params: Optional[dict] = None) -> Any:
        if uri_params and "id" in uri_params:
            return self._documents.get(uri_params["id"])
        if uri_params and "tier" in uri_params:
            return [d.__dict__ for d in self.get_by_tier(int(uri_params["tier"]))]
        return [d.__dict__ for d in self.get_all()]

    async def write(self, data: Any, uri_params: Optional[dict] = None) -> bool:
        if isinstance(data, dict):
            self.add_document(KnowledgeDocument(**data))
            return True
        if isinstance(data, list):
            self.add_documents([KnowledgeDocument(**d) for d in data])
            return True
        return False

    def count(self) -> int:
        return len(self._documents)
