# ClearLens — Phase 2 Performance Optimization (Target: <2 Second User Response)

You are working on the ClearLens backend.

Phase 1 focused on optimizing the existing implementation (metadata retrieval, transcript retrieval, caching, async improvements, HTTP client reuse, etc.).

Phase 2 is about **changing the pipeline execution strategy** while preserving the same functionality.

The objective is:

> **When a user clicks "Verify" on a YouTube Short, the response should ideally appear within 2 seconds.**

Do NOT redesign the entire project.

Do NOT introduce OCR or RAG.

Do NOT implement monitoring, Kubernetes, PostgreSQL migration, or microservices.

Focus only on making the current AI pipeline significantly faster.

---

# Current Pipeline

```text
User clicks Verify
        │
        ▼
Metadata
        │
        ▼
Transcript
        │
        ▼
Claim Extraction
        │
        ▼
Classification
        │
        ▼
Reasoning
        │
        ▼
Trust Score
        │
        ▼
Result
```

Although Phase 1 optimized several components, there are still unnecessary sequential operations and multiple network round trips.

The goal of this phase is to redesign **execution order**, not business logic.

---

# TASK 1 — Merge LLM Calls

Currently the pipeline performs three separate LLM requests:

* Claim Extraction
* Claim Classification
* Reasoning

This creates three independent API round trips.

Implement a single structured prompt that performs all three tasks in one request.

The LLM should return structured JSON similar to:

```json
{
  "video_summary": "...",
  "claims": [
    {
      "claim": "...",
      "category": "...",
      "risk_level": "...",
      "requires_verification": true,
      "verdict": "...",
      "confidence": 0.91,
      "explanation": "...",
      "key_factors": [
        "...",
        "..."
      ]
    }
  ]
}
```

Trust scoring should continue running locally after this response.

Do NOT remove the existing services.

Instead:

* keep ClaimService
* keep ClassifierService
* keep ReasoningService

but allow the orchestrator to use a single optimized execution path.

Maintain backwards compatibility.

---

# TASK 2 — Transcript Prefetch

The Chrome Extension already detects when the user is watching a Short.

Instead of waiting until the user presses Verify:

Immediately send the video ID to the backend.

The backend should:

* fetch metadata
* fetch transcript
* cache transcript

before the user clicks Verify.

When Verify is clicked:

Transcript should already exist in cache.

The Verify button should never wait for transcript extraction unless prefetch failed.

Do NOT change extension UI.

Only improve background behavior.

---

# TASK 3 — Intelligent Cache

Expand caching.

Cache separately:

* metadata
* transcript
* final analysis

Cache key:

video_id

Cache TTL should be configurable.

If an identical video has already been analyzed:

Return cached analysis immediately.

Do not call any LLM.

---

# TASK 4 — Pipeline Scheduler

The orchestrator currently executes stages sequentially.

Refactor it into a dependency-aware scheduler.

Example:

Metadata
│
├── Transcript
├── Cache Lookup
└── Background Preparation

Only execute stages whose dependencies are satisfied.

Avoid unnecessary sequential waits.

---

# TASK 5 — Background Preparation

As soon as the extension recognizes a Short:

Prepare everything possible before the user interacts.

Examples:

* metadata
* transcript
* transcript cleanup
* cache initialization

Do NOT perform expensive reasoning until Verify is clicked.

---

# TASK 6 — Faster Prompt Design

Review the combined prompt.

Reduce unnecessary tokens.

Keep:

* few-shot examples only if necessary
* concise instructions
* compact JSON schema

The objective is lower token count while maintaining output quality.

---

# TASK 7 — Persistent Model Context

Review the LLM client.

Avoid rebuilding:

* prompt templates
* HTTP clients
* parsers
* JSON validators

on every request.

Reuse initialized resources wherever possible.

---

# TASK 8 — Async Pipeline

Review every service.

Ensure:

* async execution
* no blocking file operations
* no unnecessary synchronous waits
* no repeated initialization

Maintain existing interfaces.

---

# TASK 9 — Preserve Existing Architecture

Keep the current architecture:

FastAPI

↓

Analyzer

↓

Pipeline Orchestrator

↓

Service Layer

↓

Repositories

↓

Database

Do NOT introduce new architectural patterns.

Only optimize execution.

---

# Deliverables

After implementation provide:

1. Every modified file.

2. Explanation of every optimization.

3. New execution flow.

4. Before vs after timing.

Example:

```
Metadata
400ms

Transcript
0ms (cache)

Combined LLM
1.3s

Trust Score
20ms

Total
1.8s
```

5. Explain which optimization produced the largest latency reduction.

6. Verify all existing tests continue to pass.

The pipeline must remain functionally identical while significantly reducing user-perceived latency.
