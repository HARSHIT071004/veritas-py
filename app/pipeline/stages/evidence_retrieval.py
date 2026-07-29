from app.pipeline.stage import PipelineStage, StageContext, StageResult
from app.mcp.tools.retrieval import RetrievalTool


class EvidenceRetrievalStage(PipelineStage):
    name = "evidence_retrieval"
    dependencies = ["claim_analysis"]

    async def execute(self, ctx: StageContext, inputs: dict) -> StageResult:
        claim_data = inputs.get("claim_analysis", {})
        claims = claim_data.get("claims", [])

        if not claims or not ctx.rag_engine or ctx.rag_engine.document_count == 0:
            return StageResult(data={
                "evidence_docs": [],
                "evidence_count": 0,
                "method": "none",
            })

        tool = RetrievalTool(engine=ctx.rag_engine)
        all_results = []
        for c in claims[:3]:
            result = await tool.execute(query=c.get("claim", ""), top_k=3)
            all_results.extend(result.get("results", []))

        return StageResult(data={
            "evidence_docs": all_results,
            "evidence_count": len(all_results),
            "method": "hybrid",
        })
