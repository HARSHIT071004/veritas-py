# ClearLens — Phase 1 Latency Optimization (Performance First)

You are working on the ClearLens backend.

The project architecture has already been refactored into:

* FastAPI
* Service Layer
* Pipeline Orchestrator
* Repository Layer
* Dependency Injection
* Prompt Loader
* LLM Client
* Analyzer
* Chrome Extension

The current AI pipeline is stable and functionally correct.

Current flow:

```
Chrome Extension
      │
      ▼
FastAPI
      │
Analyzer
      │
PipelineOrchestrator
      │
TranscriptService
      │
ClaimService
      │
ClassifierService
      │
ReasoningService
      │
TrustService
      ▼
Result
```

The problem is **latency**, not correctness.

Current QA report:

* Metadata Download → ~14 seconds
* Transcript Extraction (Whisper) → ~14 seconds
* Claim Extraction → ~1.2 sec
* Classification → ~1.2 sec
* Reasoning → ~1.3 sec

Total ≈ 32 seconds.

Almost 90% of the latency occurs **before the first LLM call**.

Our immediate objective is to reduce latency as much as possible **without changing the business logic**.

Ignore OCR.

Ignore RAG.

Ignore monitoring.

Ignore production deployment.

Ignore Kubernetes.

Ignore PostgreSQL migration.

Ignore Redis cluster scaling.

Ignore microservices.

Only optimize the current monolithic architecture.

---

# Goal

Reduce average response time from

```
~32 seconds
```

to

```
<8 seconds
```

without changing the pipeline output.

Do not sacrifice correctness.

---

# IMPORTANT

Do NOT redesign the project.

Do NOT rewrite the architecture.

Only optimize the existing implementation.

Every optimization should preserve the same API contracts and the same response schema.

---

# TASK 1 — Investigate Metadata Download

Current timing:

```
≈14 seconds
```

This is far too slow.

Metadata retrieval should normally complete in under 500ms.

Review the implementation inside the TranscriptService and any helper utilities.

Check whether yt-dlp is unnecessarily downloading webpage resources or media.

Optimize metadata extraction.

Possible optimizations include:

* extract_flat=True
* skip_download=True
* quiet=True
* avoid unnecessary requests
* reuse extractor instance if possible

The goal is metadata retrieval in under 500ms.

---

# TASK 2 — Improve Transcript Retrieval Strategy

Current pipeline:

```
Whisper
```

is being used even when official YouTube captions may exist.

Implement the following priority:

```
Official YouTube Transcript

↓

Official translated transcript (if available)

↓

Groq Whisper

↓

OpenAI Whisper

↓

Transcript unavailable
```

Never invoke Whisper if an official transcript already exists.

The transcript service should return the same output schema.

Do not modify downstream services.

---

# TASK 3 — Reuse HTTP Connections

Inspect every external API call.

Avoid creating new HTTP connections for every request.

Use a persistent AsyncClient (httpx.AsyncClient or equivalent).

Reuse connections for:

* Groq
* OpenRouter
* OpenAI
* Transcript APIs

Avoid repeated TLS handshakes.

Keep connections alive.

---

# TASK 4 — Optimize Prompt Size

Do not change prompt logic.

Instead:

* remove duplicated transcript lines
* normalize whitespace
* remove filler words when safe
* reduce unnecessary prompt tokens

Keep extracted meaning identical.

Goal:

Smaller prompt.

Lower inference latency.

---

# TASK 5 — Parallelize Independent Operations

Review the pipeline.

Run independent work concurrently whenever possible.

Examples:

* metadata extraction
* transcript lookup
* cache lookup

Do NOT parallelize steps that have dependencies.

Maintain deterministic outputs.

---

# TASK 6 — Improve Cache Usage

Implement smarter caching.

Cache by:

```
video_id
```

Store:

* transcript
* metadata
* final analysis (when available)

If a transcript already exists in cache:

Skip transcript extraction entirely.

Cache TTL should be configurable.

Do not change cache interfaces.

---

# TASK 7 — Profile the Pipeline

Instrument every stage.

Record timings for:

* metadata
* transcript
* claim extraction
* classification
* reasoning
* trust scoring
* total

Return these timings in the existing diagnostics.

Identify slow functions.

Do not remove existing timing collection.

Improve it.

---

# TASK 8 — Remove Unnecessary Blocking Code

Review the entire request path.

Find:

* synchronous network calls
* blocking sleeps
* unnecessary waits
* repeated object creation
* repeated initialization

Convert to async where appropriate.

Avoid duplicate initialization of expensive objects.

---

# TASK 9 — Keep API Contracts Stable

Do NOT change:

* API routes
* request schemas
* response schemas
* service interfaces
* orchestrator interfaces
* repository interfaces

Only improve performance internally.

---

# Deliverables

After implementation provide:

1. Every file modified.

2. Explanation of each optimization.

3. Before vs after latency.

Example:

```
Metadata:
14.3s
↓

0.4s

Transcript:
14.2s
↓

1.8s

Claim Extraction:
1.25s
↓

1.1s

Classification:
1.2s
↓

1.0s

Reasoning:
1.3s
↓

1.1s

Total:
32s
↓

7s
```

4. Explain which optimizations produced the biggest improvement.

5. Ensure all existing tests continue to pass.

Do not introduce breaking changes.

The priority is **performance optimization while preserving the current architecture and behavior**.
