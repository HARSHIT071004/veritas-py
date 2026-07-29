from app.pipeline.stage import PipelineStage, StageContext, StageResult


class ResponseBuilderStage(PipelineStage):
    name = "response_builder"
    dependencies = ["trust_score", "claim_analysis", "context_builder"]

    async def execute(self, ctx: StageContext, inputs: dict) -> StageResult:
        trust = inputs.get("trust_score", {})
        claims = inputs.get("claim_analysis", {})
        context = inputs.get("context_builder", {})

        return StageResult(data={
            "video_id": ctx.video_id,
            "claim": trust.get("claim", ""),
            "verdict": trust.get("verdict", "unverifiable"),
            "confidence": trust.get("trust_score", 0.0),
            "trust_label": trust.get("trust_label", "very low"),
            "explanation": trust.get("explanation", ""),
            "risk_level": trust.get("risk_level", "medium"),
            "key_factors": trust.get("key_factors", []),
            "sources": trust.get("sources", []),
            "transcript_source": context.get("transcript_source"),
            "transcript_used": context.get("transcript_available", False),
            "ocr_used": context.get("ocr_used", False),
            "claims_list": claims.get("claims", []),
            "video_summary": claims.get("video_summary", ""),
        })
