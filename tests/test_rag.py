import pytest
from app.mcp.tools.retrieval import RetrievalTool


@pytest.mark.asyncio
async def test_retrieval_tool_no_collection():
    tool = RetrievalTool()
    result = await tool.execute(query="test query")
    assert "results" in result
    assert result["total"] == 0


@pytest.mark.asyncio
async def test_retrieval_tool_spec():
    tool = RetrievalTool()
    assert tool.spec.name == "retrieve_evidence"
    assert "query" in tool.spec.input_schema["required"]
