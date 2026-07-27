# ClearLens

AI-powered misinformation detection for YouTube Shorts.

Extracts transcript (YouTube API + Groq Whisper fallback) and on-screen text (OCR), extracts factual claims via LLM, retrieves evidence from a knowledge base, and scores trust.

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
Extension (content.js) ←→ API (FastAPI) ←→ MCP Server ←→ Tools
                                                    ├── Transcript (YouTube API → Groq Whisper)
                                                    ├── Vision/OCR (OpenCV + PaddleOCR/EasyOCR/Gemini)
                                                    ├── Claim Extractor (OpenRouter)
                                                    ├── RAG Retrieval
                                                    └── LLM Reasoner (OpenRouter)
                                               ←→ Resources
                                                    ├── Knowledge Base
                                                    └── Cache
```

## Pipeline

The analysis runs in 4 parallel phases:

1. **Phase 1** — STT + OCR run concurrently via `asyncio.gather`
2. **Phase 2** — Context Builder merges transcript, OCR text, and video metadata
3. **Phase 3** — Sequential LLM pipeline: claim extraction → RAG retrieval → reasoning
4. **Phase 4** — Trust scoring

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | /api/v1/analyze | Analyze a YouTube Short |
| GET | /api/v1/history | Get user's analysis history |
| POST | /api/v1/feedback | Submit feedback on a result |
| GET | /api/v1/health | Health check |

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
│   ├── routes.py        # HTTP API endpoints
│   └── deps.py          # Dependencies
├── llm/
│   └── client.py        # Shared LLM client (OpenRouter → OpenAI)
├── vision/
│   ├── frames.py         # OpenCV frame extraction from video
│   ├── easy_ocr.py       # EasyOCR wrapper
│   ├── paddle_ocr.py     # PaddleOCR wrapper
│   └── paddle_ocr_vl.py  # PaddleOCR-VL wrapper
├── mcp/
│   ├── server.py        # MCP tool & resource registry
│   ├── tools/
│   │   ├── transcript.py    # YouTube API → Groq Whisper
│   │   ├── vision.py        # OCR pipeline
│   │   ├── claim_extractor.py # LLM-based claim extraction
│   │   ├── retrieval.py     # RAG evidence retrieval
│   │   └── reason.py        # LLM-based reasoning + verdict
│   └── resources/
│       ├── knowledge.py  # Knowledge base queries
│       └── cache.py      # Result caching
├── pipeline/
│   ├── analyzer.py      # 4-phase analysis orchestration
│   └── trust.py         # Confidence scoring
└── data/
    ├── database.py      # SQLite operations
    └── models.py        # Data models
extension/               # Chrome Extension
seed/
    └── knowledge.py     # Seed knowledge base
```
