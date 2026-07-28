import pytest
from app.mcp.tools.transcript import TranscriptTool


@pytest.mark.asyncio
async def test_transcript_tool_spec():
    tool = TranscriptTool()
    assert tool.spec.name == "extract_transcript"
    assert "video_id" in tool.spec.input_schema["required"]


@pytest.mark.asyncio
async def test_transcript_tool_returns_dict():
    tool = TranscriptTool()
    result = await tool.execute(video_id="invalid_test_id")
    assert "text" in result
    assert "source" in result
    assert "language" in result
