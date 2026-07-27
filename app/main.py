from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from app.config import settings
from app.data.database import Database
from app.data.cache import RedisCache
from app.rag.engine import RAGEngine
from app.rag.ingestion import IngestionPipeline
from app.mcp.server import MCPServer
from app.mcp.tools.transcript import TranscriptTool
from app.mcp.tools.vision import VisionTool
from app.mcp.tools.retrieval import RetrievalTool
from app.mcp.tools.reason import ReasonTool
from app.mcp.tools.claim_extractor import ClaimExtractorTool
from app.mcp.tools.classifier import ClassifierTool
from app.mcp.resources.knowledge import KnowledgeResource
from app.mcp.resources.cache import CacheResource
from app.api.routes import router as api_router
from app.auth.routes import router as auth_router

from app.api.deps import app_state
from app.pipeline.analyzer import Analyzer
from app.middleware.logging import setup_logging
from app.middleware.error_handler import ErrorHandlerMiddleware, RequestValidationMiddleware
from app.middleware.rate_limit import RateLimitMiddleware
from seed.knowledge import seed_knowledge_base

mcp: MCPServer = None
rag_engine: RAGEngine = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global mcp, rag_engine

    logger = setup_logging(settings.log_level, settings.log_file)
    Path("data").mkdir(exist_ok=True)

    logger.info("Starting ClearLens server", extra={"port": settings.port, "debug": settings.debug})

    db = Database(settings.database_path)
    redis_cache = RedisCache()
    if redis_cache._enabled:
        logger.info("Redis is enabled and configured")
    else:
        logger.warning("Redis is not available — caching, job queue, and rate limiting will be disabled")

    rag_engine = RAGEngine(persist_dir=settings.rag_persist_dir)
    loaded = rag_engine.load()
    if loaded:
        logger.info(f"RAG engine loaded from disk ({rag_engine.document_count} docs)")
    else:
        logger.info("RAG engine initialized (empty, seed with documents)")

    mcp = MCPServer()

    mcp.register_tool(TranscriptTool())
    mcp.register_tool(VisionTool())
    mcp.register_tool(RetrievalTool(engine=rag_engine))
    mcp.register_tool(ReasonTool())
    mcp.register_tool(ClaimExtractorTool())
    mcp.register_tool(ClassifierTool())

    knowledge = KnowledgeResource()
    cache_res = CacheResource(db)
    mcp.register_resource(knowledge)
    mcp.register_resource(cache_res)

    if knowledge.count() == 0 and rag_engine.document_count == 0:
        seed_knowledge_base(knowledge)
        docs = [
            {"id": d.id, "content": d.content, "source": d.source, "source_tier": d.source_tier, "title": d.title}
            for d in knowledge.get_all()
        ]
        if docs:
            await rag_engine.ingest(docs)
            logger.info(f"Seeded RAG engine with {len(docs)} knowledge documents")

    ingestion_pipeline = IngestionPipeline(rag_engine)
    app_state.init(db=db, cache=redis_cache)

    app.add_middleware(RateLimitMiddleware, redis_cache=redis_cache)

    logger.info("Server startup complete", extra={"tools": len(mcp.list_tools()), "resources": len(mcp.list_resources())})

    yield

    if redis_cache:
        await redis_cache.close()
    logger.info("Server shutting down")


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(ErrorHandlerMiddleware)
app.add_middleware(RequestValidationMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["chrome-extension://*", "https://*.youtube.com", "http://localhost:*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

app.include_router(auth_router)
app.include_router(api_router, prefix="/api/v1")

ext_path = Path(__file__).parent.parent / "extension"
if ext_path.exists():
    app.mount("/extension", StaticFiles(directory=str(ext_path)), name="extension")


@app.get("/")
async def root():
    landing = Path(__file__).parent.parent / "extension" / "landing" / "index.html"
    if landing.exists():
        from fastapi.responses import HTMLResponse
        return HTMLResponse(content=landing.read_text(encoding="utf-8"), status_code=200)
    return {"app": settings.app_name, "status": "running"}


@app.get("/api/status")
async def api_status():
    return {
        "app": settings.app_name,
        "version": "1.0.0",
        "tools": mcp.list_tools() if mcp else [],
        "resources": mcp.list_resources() if mcp else [],
        "rag_docs": rag_engine.document_count if rag_engine else 0
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=settings.debug)
