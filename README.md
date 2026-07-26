# ClearLens

AI-powered misinformation detection for YouTube Shorts.

## Quick Start

```bash
cp .env.example .env
# Edit .env with your API keys
docker compose up -d
```

Or without Docker:

```bash
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your API keys
uvicorn app.main:app --reload
```

## Architecture

```
Extension (content.js) ←→ API (FastAPI) ←→ MCP Server ←→ Tools
                                                   ├── Transcript
                                                   ├── Vision/OCR
                                                   ├── RAG Retrieval
                                                   └── LLM Reasoner
                                              ←→ Resources
                                                   ├── Knowledge Base
                                                   └── Cache
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | /api/v1/analyze | Analyze a YouTube Short |
| GET | /api/v1/history | Get user's analysis history |
| POST | /api/v1/feedback | Submit feedback on a result |
| GET | /api/v1/health | Health check |

## Project Structure

```
app/
├── main.py              # FastAPI entry point
├── config.py            # Environment configuration
├── api/
│   ├── routes.py        # HTTP API endpoints
│   └── deps.py          # Dependencies (rate limiting)
├── mcp/
│   ├── server.py        # MCP tool & resource registry
│   ├── tools/           # MCP tools (transcript, vision, retrieval, reason)
│   └── resources/       # MCP resources (knowledge base, cache)
├── pipeline/
│   ├── analyzer.py      # Analysis orchestration
│   └── trust.py         # Confidence scoring
└── data/
    ├── database.py      # SQLite operations
    └── models.py        # Data models
extension/               # Chrome Extension
seed/
    └── knowledge.py     # Seed knowledge base
```
