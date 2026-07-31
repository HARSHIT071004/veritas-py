from app.pipeline.stage import PipelineStage, StageContext, StageResult
from app.mcp.tools.retrieval import RetrievalTool
from app.services.web_evidence_service import WebEvidenceService


class EvidenceRetrievalStage(PipelineStage):
    name = "evidence_retrieval"
    dependencies = ["claim_analysis"]

    def __init__(self):
        super().__init__()
        self._web_svc = WebEvidenceService()

    async def execute(self, ctx: StageContext, inputs: dict) -> StageResult:
        claim_data = inputs.get("claim_analysis", {})
        claims = claim_data.get("claims", [])
        video_summary = claim_data.get("video_summary", "")

        rag_docs = []
        if claims and ctx.rag_engine and ctx.rag_engine.document_count > 0:
            tool = RetrievalTool(engine=ctx.rag_engine)
            for c in claims[:3]:
                result = await tool.execute(query=c.get("claim", ""), top_k=3)
                rag_docs.extend(result.get("results", []))

        web_result = await self._web_svc.collect(claims, video_summary)
        web_docs = web_result.get("web_evidence", [])

        evidence_docs = list(rag_docs) + list(web_docs)

        if not evidence_docs:
            return StageResult(data={
                "evidence_docs": [],
                "evidence_count": 0,
                "method": "none",
                "rag_evidence": [],
                "web_evidence": [],
                "web_evidence_count": 0,
                "web_status": web_result.get("status", "empty"),
            })

        return StageResult(data={
            "evidence_docs": evidence_docs,
            "evidence_count": len(evidence_docs),
            "method": "hybrid" if rag_docs and web_docs else ("rag" if rag_docs else "web"),
            "rag_evidence": rag_docs,
            "web_evidence": web_docs,
            "web_evidence_count": len(web_docs),
            "web_status": web_result.get("status", "empty"),
        })
