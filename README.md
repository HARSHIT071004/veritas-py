# ClearLens

AI-powered misinformation detection for YouTube Shorts.

Extracts transcript (YouTube API + Groq Whisper fallback), on-screen text (OCR), extracts factual claims via LLM, retrieves evidence from a knowledge base, and scores trust.

## Quick Start

```bash
cp .env.example .env
# Edit .env with your API keys (OpenRouter, Groq, OpenAI, Gemini)
pip install -r requirements.txt
python -m app.main
```

Or with Docker:

```bash
cp .env.example .env
docker compose up -d
```

## Architecture

```
Extension (content.js) ←→ API (FastAPI) ←→ Pipeline Orchestrator ←→ 9 Pipeline Stages
                                                                        ├── video_detection
                                                                        ├── metadata
                                                                        ├── transcript
                                                                        ├── visual_analysis
                                                                        ├── context_builder
                                                                        ├── claim_analysis
                                                                        ├── evidence_retrieval
                                                                        ├── trust_score
                                                                        └── response_builder
                                                                   ←→ Services
                                                                        ├── TranscriptService (YouTube API → Groq Whisper)
                                                                        ├── ClaimService (LLM extraction)
                                                                        ├── ClassifierService (LLM classification)
                                                                        ├── ReasoningService (LLM verdict)
                                                                        └── TrustService (confidence scoring)
                                                                   ←→ MultiLevelCache (L1/L2/L3)
                                                                   ←→ RAG Engine (FAISS + BM25)
```

## Pipeline

The pipeline runs as a **DAG of 9 stages** with automatic dependency resolution. Independent stages execute in parallel:

```
Level 0: [video_detection]
Level 1: [metadata, transcript, visual_analysis]  ← parallel
Level 2: [context_builder]
Level 3: [claim_analysis]                          ← combined LLM path
Level 4: [evidence_retrieval]                      ← RAG search
Level 5: [trust_score]                             ← reasoning + trust
Level 6: [response_builder]
```

Each stage supports:
- **Clear input/output** — typed `StageContext` / `StageResult`
- **Async execution** — `asyncio.gather` for concurrent levels
- **Multi-level caching** — L1 (in-memory LRU) → L2 (Redis) → L3 (SQLite)
- **Retries** — exponential backoff per stage
- **Timing metrics** — per-stage millisecond timing exposed in response

### Prefetch

As soon as a YouTube Short becomes visible, the extension sends a prefetch request (`POST /api/v1/prefetch`). The backend immediately starts transcript extraction and metadata fetch in the background. When the user clicks Verify, data is already cached — eliminating the dominant latency bottleneck.

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | /api/v1/prefetch | Prefetch transcript + metadata (background) |
| POST | /api/v1/analyze | Analyze a YouTube Short (sync) |
| POST | /api/v1/analyze/async | Submit analysis job (requires Redis) |
| GET | /api/v1/result/{job_id} | Poll async job result |
| GET | /api/v1/history | Get user's analysis history |
| POST | /api/v1/feedback | Submit feedback on a result |
| GET | /api/v1/health | Health check |

### Analysis Modes

| Mode | Model | Use Case |
|------|-------|----------|
| `fast` | `llama-3.1-8b-instant` (Groq) | Quick preview, lower accuracy |
| `balanced` | OpenRouter default | Default — single combined LLM call |
| `accurate` | OpenRouter default | Full sequential pipeline, highest accuracy |

## Required API Keys

| Service | Used For | Required |
|---------|----------|----------|
| OpenRouter | Claim extraction + reasoning via LLM | Yes |
| Groq | Hindi/English speech transcription (Whisper) | Recommended |
| OpenAI | STT fallback (Whisper) or LLM fallback | Optional |
| Gemini | OCR fallback for on-screen text | Optional |

## Project Structure

```
app/
├── main.py              # FastAPI entry point
├── config.py            # Environment configuration
├── api/
│   ├── routes.py        # HTTP API endpoints (analyze, prefetch, history, feedback)
│   └── deps.py          # Dependencies (db, cache, analyzer, pipeline_cache)
├── llm/
│   ├── client.py        # Shared LLM client (OpenRouter → Groq → OpenAI)
│   ├── prompt_loader.py # Prompt template loader with caching
│   └── prompts/         # Prompt templates (claim_extraction, classification, reasoning, combined_analysis)
├── pipeline/
│   ├── stage.py         # Abstract PipelineStage base class
│   ├── cache.py         # MultiLevelCache (L1 in-memory, L2 Redis, L3 SQLite)
│   ├── orchestrator.py  # Stage DAG execution engine with dependency resolution
│   ├── analyzer.py      # API-facing analysis orchestrator with request dedup
│   └── stages/          # 9 independent pipeline stages
│       ├── video_detection.py
│       ├── metadata.py
│       ├── transcript.py
│       ├── visual_analysis.py
│       ├── context_builder.py
│       ├── claim_analysis.py
│       ├── evidence_retrieval.py
│       ├── trust_score.py
│       └── response_builder.py
├── services/
│   ├── transcript_service.py  # YouTube API → Whisper (Groq/OpenAI)
│   ├── claim_service.py       # LLM-based claim extraction
│   ├── classifier_service.py  # LLM-based claim classification
│   ├── reasoning_service.py   # LLM-based reasoning + verdict
│   └── trust_service.py       # Confidence scoring algorithm
├── vision/
│   ├── frames.py         # OpenCV frame extraction from video
│   ├── easy_ocr.py       # EasyOCR wrapper
│   ├── paddle_ocr.py     # PaddleOCR wrapper
│   └── paddle_ocr_vl.py  # PaddleOCR-VL wrapper
├── rag/
│   ├── engine.py         # FAISS + BM25 + cross-encoder hybrid search
│   ├── embeddings.py     # Sentence transformer embeddings
│   └── ingestion.py      # Document chunking + ingestion pipeline
├── mcp/
│   ├── server.py         # MCP tool & resource registry
│   ├── tools/            # Transcript, Vision, Retrieval, Reason, ClaimExtractor, Classifier
│   └── resources/        # Knowledge base, Cache
├── data/
│   ├── database.py       # SQLite operations (users, cache, history, feedback)
│   ├── cache.py          # Redis async client wrapper
│   ├── models.py         # Dataclass definitions
│   └── repositories/     # AnalysisRepository, UserRepository
├── auth/
│   ├── routes.py         # Register, login, refresh token
│   └── dependencies.py   # JWT authentication
├── middleware/
│   ├── logging.py        # Structured logging
│   ├── error_handler.py  # Global exception handling
│   └── rate_limit.py     # Token bucket rate limiter
├── worker.py             # Async job queue (arq)
└── evaluation/           # Test runner + dataset
extension/               # Chrome Extension (content script, background, popup)
seed/
    └── knowledge.py     # Knowledge base seeding
```
