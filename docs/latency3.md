# ClearLens — Phase 3: High-Performance Backend & User Experience

## Objective

Phase 1 optimized the current implementation.

Phase 2 redesigned the execution flow to minimize latency.

Phase 3 focuses on making the system feel **instant**, highly reliable, and capable of handling thousands of concurrent users while keeping the current monolithic architecture.

Ignore the following completely:

* OCR
* RAG
* Kubernetes
* Microservices
* PostgreSQL migration
* Monitoring/Observability
* CI/CD
* Docker improvements

Only improve the current FastAPI + Chrome Extension architecture.

The goal is a backend that feels production-ready and delivers the fastest possible user experience.

---

# Current Architecture

```text
Chrome Extension
        │
        ▼
FastAPI
        │
Analyzer
        │
PipelineOrchestrator
        │
Transcript Service
        │
LLM Analysis
        │
Trust Score
        ▼
Result
```

---

# TASK 1 — Background Prefetch Engine

The Chrome Extension already detects YouTube Shorts before the user clicks Verify.

Implement a background preparation engine.

As soon as a Short is detected:

* send the video_id silently
* fetch metadata
* fetch transcript
* clean transcript
* cache transcript
* store metadata

Do NOT perform LLM analysis yet.

When the user clicks Verify, transcript retrieval should already be complete.

If preparation fails, gracefully fall back to the normal pipeline.

---

# TASK 2 — Smart Multi-Level Cache

Implement a cache hierarchy.

Level 1

In-memory cache

Store:

* transcript
* metadata
* recent analyses

Level 2

Redis (when available)

Level 3

SQLite fallback

Every cache entry should use:

video_id

Invalidate using configurable TTL.

Never repeat expensive work if cached data exists.

---

# TASK 3 — Request Deduplication

If multiple users verify the same YouTube Short simultaneously:

Current behavior:

```text
10 users

↓

10 transcript requests

↓

10 LLM requests
```

New behavior:

```text
10 users

↓

1 transcript request

↓

1 LLM request

↓

share result

↓

all users receive same response
```

Implement an in-flight request registry.

If a job already exists for a video_id:

New requests should subscribe to the existing job instead of creating another.

---

# TASK 4 — Fast Pipeline Scheduler

Refactor the PipelineOrchestrator into a dependency-aware scheduler.

Only execute stages that are actually required.

Example:

If transcript exists in cache:

Skip transcript service.

If analysis exists in cache:

Return immediately.

Avoid unnecessary computation.

---

# TASK 5 — Intelligent Background Analysis

Introduce optional proactive analysis.

When a user watches a Short for a configurable duration (for example 2–3 seconds):

The extension may begin background analysis.

If the user eventually clicks Verify:

Return the completed result instantly.

This feature should be configurable and easy to disable.

---

# TASK 6 — Adaptive LLM Strategy

Support multiple execution modes.

Fast Mode

* lightweight model
* optimized prompt
* quickest response

Balanced Mode

* current default

Accurate Mode

* stronger reasoning model
* slower but higher quality

The orchestrator should be able to select the execution mode without changing downstream services.

---

# TASK 7 — Robust Error Recovery

Ensure every stage fails gracefully.

If metadata fails:

Attempt transcript directly.

If transcript fails:

Return a meaningful "Transcript unavailable" response.

If the LLM provider fails:

Use the fallback provider.

If every provider fails:

Return a structured error object instead of crashing.

Never expose internal exceptions to the frontend.

---

# TASK 8 — Chrome Extension UX Improvements

Improve the Verify experience.

Instead of a static loading spinner:

Display progress updates such as:

* Preparing video
* Fetching transcript
* Analyzing claims
* Generating verdict
* Finalizing result

If the result is already cached:

Display it immediately.

Support graceful retry if the request temporarily fails.

---

# TASK 9 — Performance Profiling

Expand timing collection.

Track:

* cache lookup
* metadata retrieval
* transcript retrieval
* transcript cleaning
* LLM request
* trust scoring
* total pipeline time

Generate a performance report for every analysis.

This should make future optimization straightforward.

---

# TASK 10 — Preserve Existing Architecture

Do NOT redesign the application.

Keep:

FastAPI

↓

Analyzer

↓

PipelineOrchestrator

↓

Service Layer

↓

Repositories

↓

Database

Do not change API contracts.

Do not modify response schemas.

Only improve execution efficiency, concurrency, caching, resilience, and user experience.

---

# Expected Deliverables

Provide:

1. Every modified file.

2. Explanation of every optimization.

3. Updated pipeline diagram.

4. Before vs After execution flow.

Example:

```text
User opens Short
        │
        ▼
Background Prefetch
        │
        ▼
Transcript Cached
        │
User clicks Verify
        │
        ▼
Cache Lookup
        │
        ▼
Single LLM Analysis
        │
        ▼
Trust Score
        │
        ▼
Result (<2 seconds)
```

5. Explain which optimizations contributed the most to reducing latency.

6. Ensure all existing tests continue to pass and no API contracts are broken.

The outcome of Phase 3 should be a backend that feels nearly instantaneous for repeat analyses, efficiently handles concurrent users, avoids duplicate work, and provides a smooth user experience while preserving the existing architecture.
