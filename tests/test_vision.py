import pytest
from app.mcp.tools.vision import VisionTool


@pytest.mark.asyncio
async def test_vision_tool_skips_when_no_vision_needed():
    tool = VisionTool()
    result = await tool.execute(
        video_id="test123",
        claim_text="this is a simple spoken claim with no reference to images"
    )
    assert result["used"] is False
    assert result["reason"] == "skipped"


@pytest.mark.asyncio
async def test_vision_tool_triggers_on_visual_keywords():
    tool = VisionTool()
    result = await tool.execute(
        video_id="test123",
        claim_text="this image shows a fake screenshot"
    )
    assert result["used"] is True
