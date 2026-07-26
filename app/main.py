from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from app.config import settings
from app.data.database import Database
from app.mcp.server import MCPServer
from app.mcp.tools.transcript import TranscriptTool
from app.mcp.tools.vision import VisionTool
from app.mcp.tools.retrieval import RetrievalTool
from app.mcp.tools.reason import ReasonTool
from app.mcp.resources.knowledge import KnowledgeResource
from app.mcp.resources.cache import CacheResource
from app.api.routes import router, analyzer as analyzer_ref, db as db_ref
from app.pipeline.analyzer import Analyzer
from seed.knowledge import seed_knowledge_base

db: Database = None
mcp: MCPServer = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global db, mcp

    Path("data").mkdir(exist_ok=True)

    db = Database(settings.database_path)

    mcp = MCPServer()

    transcript_tool = TranscriptTool()
    vision_tool = VisionTool()
    retrieval_tool = RetrievalTool()
    reason_tool = ReasonTool()

    mcp.register_tool(transcript_tool)
    mcp.register_tool(vision_tool)
    mcp.register_tool(retrieval_tool)
    mcp.register_tool(reason_tool)

    knowledge = KnowledgeResource()
    cache_res = CacheResource(db)
    mcp.register_resource(knowledge)
    mcp.register_resource(cache_res)

    if knowledge.count() == 0:
        seed_knowledge_base(knowledge)

    retrieval_tool._collection = None
    retrieval_tool._embedding_fn = None

    analyzer = Analyzer(mcp, db)

    import app.api.routes as routes
    routes.analyzer = analyzer
    routes.db = db

    yield

    db = None
    mcp = None


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["chrome-extension://*", "https://*.youtube.com"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1")

ext_path = Path(__file__).parent.parent / "extension"
if ext_path.exists():
    app.mount("/extension", StaticFiles(directory=str(ext_path)), name="extension")


@app.get("/")
async def root():
    return {
        "app": settings.app_name,
        "docs": "/docs",
        "tools": mcp.list_tools() if mcp else [],
        "resources": mcp.list_resources() if mcp else []
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=settings.debug)
