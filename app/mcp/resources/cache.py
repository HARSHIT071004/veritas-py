from typing import Optional, Any
from app.mcp.resources.base import Resource, ResourceSpec
from app.data.database import Database


class CacheResource(Resource):
    spec = ResourceSpec(
        uri="cache://results",
        name="Analysis Cache",
        description="Cached analysis results keyed by video_id"
    )

    def __init__(self, db: Database):
        self._db = db

    async def read(self, uri_params: Optional[dict] = None) -> Any:
        if uri_params and "video_id" in uri_params:
            return self._db.get_cached(uri_params["video_id"])
        return None

    async def write(self, data: Any, uri_params: Optional[dict] = None) -> bool:
        if isinstance(data, dict) and "video_id" in data:
            video_id = data.pop("video_id", None)
            if video_id:
                self._db.set_cache(str(video_id), data)
                return True
        return False
