# ClearLens Latency Optimization Plan — 20s → ≤2s

Based on `design10.md` requirements.

## Current Breakdown

| Phase | Current Time | % of Total |
|-------|-------------|-----------|
| Metadata download (yt-dlp) | ~2.6s | 13% |
| Transcript (yt-dlp → ffmpeg → Whisper) | ~13.5s | 67% |
| Claim extraction (LLM) | ~1.3s | 7% |
| Classification (LLM) | ~1.0s | 5% |
| Reasoning (LLM) | ~1.5s | 8% |
| Trust score | ~0s | 0% |
| **Total** | **~20s** | **100%** |

## Dependency DAG (Target)

```
User lands on Short
  │
  ├── Extension detects navigation (MutationObserver, already works)
  │     ├── Extract video_id from URL
  │     ├── Assess risk locally (instant)
  │     └── If risk is medium/high → START PREFETCH
  │
  ├── PREFETCH Phase (before user clicks, ~0s visible latency):
  │     ├── Fetch metadata (YouTube no-cookie page / oEmbed API)
  │     │     └── ~0.5s, cache by video_id
  │     ├── Fetch transcript (youtubetranscript.com API)
  │     │     └── ~1.5s, cache by video_id
  │     └── Store both in extension local storage
  │
  User clicks "Verify"
  │
  ├── Send video_id + prefetched metadata/transcript to FastAPI
  ├── FastAPI checks Redis/SQLite cache → HIT? Return instantly (~10ms)
  │
  ├── MISS → Pipeline runs:
  │     ├── Phase 1 (parallel):
  │     │     ├── Transcript: use prefetched + YouTube API (skip yt-dlp/Whisper entirely)
  │     │     │     └── ~0s (already fetched in prefetch)
  │     │     └── Vision/OCR: skip unless trigger keywords present
  │     │           └── ~0s (rarely triggered)
  │     │
  │     ├── Phase 2+3 (merged, single LLM call):
  │     │     ├── Claim extraction + Classification in one prompt
  │     │     └── Use fast model (Gemma 4 4B / Llama-3.1-8B via Groq)
  │     │           └── ~1.0-1.5s
  │     │
  │     ├── Phase 4 (Reasoning):
  │     │     ├── Analyze claims against transcript
  │     │     └── Use same fast model
  │     │           └── ~0.5-1.0s
  │     │
  │     └── Phase 5 (Trust score):
  │           └── Deterministic, instant
  │                 └── ~0s
  │
  └── Return result (~1.5-2.5s total after click)
```

---

## 1. Prefetch Pipeline (Extension + Backend)

**What changes:** Extension starts fetching metadata + transcript as soon as a Short appears, before the user clicks.

**Why it reduces latency:** The ~16s bottleneck (metadata + transcript) becomes invisible to the user.

### Content Script (`extension/content.js`)

Add auto-prefetch when a Short is detected:

```javascript
// After checkCurrentShort identifies a new video_id
function prefetchData(videoId) {
  // Fetch metadata from YouTube oEmbed
  fetch(`https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v=${videoId}&format=json`)
    .then(r => r.json())
    .then(data => {
      chrome.storage.session.set({ ["prefetch_meta_" + videoId]: data });
    });

  // Fetch transcript directly from youtubetranscript.com
  fetch(`https://youtubetranscript.com/api?vid=${videoId}&lang=en`)
    .then(r => r.json())
    .then(data => {
      if (Array.isArray(data)) {
        const text = data.map(s => s.text).join(" ");
        chrome.storage.session.set({ ["prefetch_transcript_" + videoId]: text });
      }
    });
}
```

When the user clicks Verify, send the pre-fetched data as part of the request so the backend skips the download entirely.

### Backend (`app/api/routes.py`)

Add optional `prefetched_transcript` and `prefetched_metadata` fields to `AnalyzeRequest`. If provided, skip yt-dlp entirely.

### Files that change:
- `extension/content.js` — add prefetch logic
- `extension/background.js` — handle `PREFETCH` message type
- `app/api/routes.py` — accept prefetched data
- `app/services/transcript_service.py` — accept pre-fetched transcript

**Complexity:** Low
**Est. impl. time:** 2-3 hours
**Latency improvement:** ~16s eliminated from user-perceived wait (moved to prefetch)
**Risks:** Prefetch bandwidth for every Short navigation; storage limit in extension

---

## 2. Transcript: YouTube API Only, Drop Whisper Fallback

**What changes:** Remove yt-dlp + ffmpeg + Groq Whisper fallback entirely. Use only `youtubetranscript.com` API.

**Why it reduces latency:** Whisper path takes ~13.5s (download audio + convert + API call). YouTube API takes ~1.5s. If the YouTube API fails, return a clear error instead of silently falling back to Whisper.

**Implementation:** In `TranscriptService.extract()`, remove `_whisper_transcribe()` calls. If `_fetch_youtube_transcript()` and `_fetch_youtube_captions()` both fail, return an error immediately.

### Files that change:
- `app/services/transcript_service.py` — remove Whisper fallback
- `app/config.py` — optional: remove `groq_stt_model` and Whisper-related keys if no longer needed

**Complexity:** Low
**Est. impl. time:** 30 min
**Latency improvement:** ~12s saved vs worst case Whisper; ~0s vs best case YouTube API
**Risks:** Some videos without YouTube captions become unanalyzable. But prefetch + caching means the Whisper path was rarely hit in practice for popular Shorts.

---

## 3. Merge Claim Extraction + Classification (One LLM Call)

**What changes:** Combine `claim_extraction.txt` and `classification.txt` prompts into a single prompt. One LLM call returns both claims with their categories.

**Why it reduces latency:** Eliminates one LLM round-trip (saves ~1.0-1.3s).

### Implementation:

Create `app/llm/prompts/claim_and_classify.txt`:

```
You are a content analysis system. Given a transcript, extract verifiable factual claims and classify each into one of these categories: [health, science, politics, technology, business, education, entertainment, general].

For each claim, return:
- claim: the exact factual statement
- risk_level: low/medium/high
- category: one of the 8 categories
- classifier_confidence: 0.0-1.0
- requires_verification: true/false

TRANSCRIPT:
{transcript}

TITLE: {title}
DESCRIPTION: {description}
CHANNEL: {channel}

Return JSON with: claims[], video_summary
```

Remove `ClassifierService.classify()` call from orchestrator. The merged response already includes category + confidence per claim.

### Files that change:
- `app/llm/prompts/claim_and_classify.txt` — new merged prompt
- `app/services/claim_service.py` — update to also classify in same call
- `app/services/classifier_service.py` — reduce to fallback-only or remove
- `app/pipeline/orchestrator.py` — remove Phase 3 (classifier call), integrate categories from Phase 2
- `app/schemas/pipeline_models.py` — `Claim` model already has `category` and `classifier_confidence` fields

**Complexity:** Medium
**Est. impl. time:** 2-3 hours
**Latency improvement:** ~1.0s saved (one fewer LLM round-trip)
**Risks:** Larger prompt = slightly slower per-call; may need model with larger context window. Quality regression possible if the model can't do both tasks well in one call.

---

## 4. Use Faster LLM Models

**What changes:** Switch from `llama-3.3-70b-versatile` (Groq) and `google/gemma-4-26b-a4b-it:free` (OpenRouter) to faster models for claims + classification. Keep the larger model only for reasoning (where quality matters most).

**Why it reduces latency:** 70B models have ~0.5-1.5s latency. 8B-12B models like `llama-3.1-8b-instant` (Groq) have ~0.2-0.5s latency. This cuts LLM time by 60-70%.

### Implementation:

In `app/llm/client.py` or in each service:
- Claims/classification: use `llama-3.1-8b-instant` (Groq, ~300ms) or `gemini-2.0-flash-lite` (OpenRouter, ~200ms)
- Reasoning: keep `llama-3.3-70b-versatile` or `gemma-4-26b-a4b-it:free` for quality

Add a `model_override` parameter to `call_llm()` so each service can specify its preferred model.

### Files that change:
- `app/llm/client.py` — add model selection per service
- `app/services/claim_service.py` — specify fast model
- `app/services/reasoning_service.py` — keep current model
- `app/config.py` — optionally add env vars for per-service model selection

**Complexity:** Medium
**Est. impl. time:** 1-2 hours
**Latency improvement:** ~1.5-2.0s saved (fast models for claims+classification+reasoning)
**Risks:** Quality regression on complex claims. The fast models may miss subtle claims or misclassify.

---

## 5. Parallel Reasoning with Claim Extraction

**What changes:** Start reasoning with the transcript and metadata immediately, in parallel with claim extraction. When claims arrive, verify them against the already-computed reasoning.

**Why it reduces latency:** Reasoning (~0.5-1.0s with fast model) currently waits for claims + classification (~2.3s). If reasoning starts in parallel with claims extraction, it can finish at roughly the same time.

### Implementation:

In `PipelineOrchestrator.run()`:

```python
# Phase 2: Start claim extraction AND reasoning in parallel
t1 = time.time()
claims_task = self.claims.extract(**context)
reasoning_task = self.reasoning.analyze(
    claim=transcript[:500],  # Use first 500 chars as "claim" for initial pass
    transcript=transcript or "",
    ocr_text=ocr_text or "",
)

claims_res, reason_res = await asyncio.gather(claims_task, reasoning_task, return_exceptions=True)

# If reasoning was done without specific claims, do a fast re-verify with actual claims
if not isinstance(reason_res, Exception) and not isinstance(claims_res, Exception) and claims_res.claims:
    reason_res = await self.reasoning.analyze(
        claim=claims_res.claims[0].claim,
        claim_category=claims_res.claims[0].category,
        transcript=transcript or "",
        ocr_text=ocr_text or "",
    )
    # This second reasoning call is cheap because it has only the specific claim
```

Alternatively, if quality is acceptable from the first parallel reasoning pass, skip the second call entirely.

### Files that change:
- `app/pipeline/orchestrator.py` — restructure Phase 2/4 into parallel execution

**Complexity:** Medium
**Est. impl. time:** 2-3 hours
**Latency improvement:** ~1.0-1.5s saved (reasoning overlaps with claims extraction)
**Risks:** First-pass reasoning without specific claims may produce lower-quality results. The second re-verify call mitigates this but adds ~0.5s.

---

## 6. Cache LLM Responses

**What changes:** Cache LLM responses keyed by (prompt_hash, model). Same video → same transcript → same prompt → cache hit.

**Why it reduces latency:** If two users analyze the same Short, the second user skips all LLM calls (saves ~2.5-3.5s).

### Implementation:

In `app/llm/client.py`:

```python
_llm_cache: dict[str, tuple[str, float]] = {}  # key -> (response, timestamp)

def _cache_key(prompt, model, temperature, max_tokens):
    import hashlib
    raw = f"{prompt}|{model}|{temperature}|{max_tokens}"
    return hashlib.md5(raw.encode()).hexdigest()

async def call_llm(prompt, ..., cache_ttl=3600):
    key = _cache_key(prompt, model, ...)
    if key in _llm_cache:
        response, ts = _llm_cache[key]
        if time.time() - ts < cache_ttl:
            return response
    # ... existing logic ...
    _llm_cache[key] = (response, time.time())
    return response
```

Also add an LRU size limit to prevent unbounded memory growth.

### Files that change:
- `app/llm/client.py` — add caching layer

**Complexity:** Low
**Est. impl. time:** 1 hour
**Latency improvement:** ~3s saved on cache hit (all LLM calls skipped)
**Risks:** Cache invalidation — if the model is updated or prompt changes, stale responses could persist. TTL mitigates this.

---

## 7. Metadata: Replace yt-dlp with YouTube oEmbed

**What changes:** Replace `yt-dlp` metadata download with YouTube's lightweight oEmbed API.

**Why it reduces latency:** `yt-dlp` requires a Python process startup + network request (~2.6s). oEmbed returns JSON in ~0.2-0.5s via a simple HTTP GET.

**Implementation:** In the backend or extension, fetch `https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json` instead of running yt-dlp.

The oEmbed response includes `title`, `author_name` (channel), `thumbnail_url`, but not `description`. For the description, fetch the page HTML with a lightweight `httpx` GET and parse the meta tags.

### Files that change:
- `app/pipeline/orchestrator.py` — or remove metadata fetch from backend if extension sends it from prefetch
- `extension/content.js` — prefetch metadata via oEmbed
- `app/llm/prompts/` — adjust context to not rely on description (oEmbed doesn't include it)

**Complexity:** Low
**Est. impl. time:** 1 hour
**Latency improvement:** ~2s saved (2.6s → ~0.5s)
**Risks:** oEmbed doesn't return description. Title + channel only. Some prompts may rely on description text.

---

## 8. Request Deduplication

**What changes:** If multiple users (or the same user multiple times) request analysis of the same video_id simultaneously, coalesce into a single pipeline run.

**Why it reduces latency:** Prevents redundant work. Second+ requesters automatically get the result when the first completes.

### Implementation:

Add an in-flight request tracker in `app/pipeline/analyzer.py` or `app/api/deps.py`:

```python
_in_flight: dict[str, asyncio.Future] = {}

async def get_or_start_analysis(video_id, metadata, user_id):
    if video_id in _in_flight:
        return await _in_flight[video_id]
    future = asyncio.get_event_loop().create_future()
    _in_flight[video_id] = future
    try:
        result = await analyzer.analyze(video_id, metadata, user_id)
        future.set_result(result)
        return result
    except Exception as e:
        future.set_exception(e)
        raise
    finally:
        del _in_flight[video_id]
```

### Files that change:
- `app/api/routes.py` — wrap analyze call with dedup
- `app/pipeline/analyzer.py` — or add dedup there

**Complexity:** Low
**Est. impl. time:** 30 min
**Latency improvement:** Second+ concurrent requests get result at same time as first (~0 added latency vs running separately)
**Risks:** If the first request fails, all deduped requests fail together.

---

## 9. Optimized LLM Client: Parallel Provider Calls

**What changes:** Instead of trying providers sequentially (Groq → OpenRouter → OpenAI), try them in parallel and use whichever responds first.

**Why it reduces latency:** If the primary provider is slow or degraded, the fallback can respond faster. Current sequential approach adds 3-9s of timeout before moving to next provider.

### Implementation:

In `app/llm/client.py`, use `asyncio.wait(..., return_when=FIRST_COMPLETED)`:

```python
async def call_llm(prompt, ...):
    tasks = []
    if settings.groq_api_key:
        tasks.append(_call_groq(prompt, ...))
    if settings.openrouter_api_key:
        tasks.append(_call_openrouter(prompt, ...))
    if settings.openai_api_key:
        tasks.append(_call_openai(prompt, ...))
    
    if not tasks:
        return None
    
    done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED, timeout=30)
    for task in done:
        result = task.result()
        if result:
            for t in pending:
                t.cancel()
            return result
    # Fall back to sequential retries
```

### Files that change:
- `app/llm/client.py` — restructure provider calls

**Complexity:** Medium
**Est. impl. time:** 1-2 hours
**Latency improvement:** Variable, 0-5s in worst-case provider degradation
**Risks:** Wasted API calls from multiple providers running simultaneously. Cost increase. Some providers charge even for incomplete responses.

---

## 10. Background Cache Warming

**What changes:** After a successful analysis, proactively analyze popular/recommended Shorts in the background to warm the cache.

**Why it reduces latency:** When a user navigates to a Short that was pre-analyzed, result is served from cache instantly.

**Implementation:** Add a background task (asyncio or arq job) that runs after each user-initiated analysis to also analyze related/recommended videos from the same channel or topic.

### Files that change:
- `app/pipeline/analyzer.py` — add background warm-up
- `app/worker.py` — optionally use arq for background jobs

**Complexity:** High
**Est. impl. time:** 4-6 hours
**Latency improvement:** Predictive — users see cached results for related content
**Risks:** Increased API costs from pre-analyzing content users may never watch. Must cap the number of pre-analyzed videos per day.

---

## Optimized Timing Estimates

### Cache Hit (after any user analyzed this video)
| Before Click | After Click | Total Perceived |
|-------------|-------------|-----------------|
| ~0s | ~10ms | **~10ms** |

### First Analysis with Prefetch
| Phase | Before Click | After Click |
|-------|-------------|-------------|
| Metadata (oEmbed) | ~0.5s | — |
| Transcript (YouTube API) | ~1.5s | — |
| Cache check | — | ~10ms |
| Merged claims+classification (8B model) | — | ~1.0s |
| Reasoning (8B model, parallel started) | — | ~0.5s |
| Trust score | — | ~0s |
| **Total** | **~2s** (hidden) | **~1.5s** |

### First Analysis without Prefetch
| Phase | Time |
|-------|------|
| Metadata (oEmbed) | ~0.5s |
| Transcript (YouTube API) | ~1.5s |
| Merged claims+classification (8B) | ~1.0s |
| Reasoning (8B, parallel with claims) | ~0.5s |
| Trust score | ~0s |
| **Total** | **~3.5s** |

If reasoning uses a larger model (e.g., 70B), add ~0.5-1.0s, bringing total to ~4-4.5s without prefetch or ~2.5s with prefetch.

---

## Prioritized Roadmap (Highest ROI First)

| # | Optimization | Est. Time | Latency Saved | Complexity | ROI |
|---|-------------|-----------|---------------|-----------|-----|
| 1 | Prefetch pipeline (extension) | 2-3h | ~16s (hidden) | Low | ★★★★★ |
| 2 | Metadata via oEmbed (replace yt-dlp) | 1h | ~2s | Low | ★★★★★ |
| 3 | Drop Whisper fallback | 30min | ~12s (worst case) | Low | ★★★★★ |
| 4 | Merge claims + classification prompts | 2-3h | ~1.0s | Medium | ★★★★ |
| 5 | Use faster LLM models (8B for claims) | 1-2h | ~1.5-2.0s | Medium | ★★★★ |
| 6 | Cache LLM responses | 1h | ~3s (cache hit) | Low | ★★★★ |
| 7 | Request deduplication | 30min | ~3s (concurrent) | Low | ★★★ |
| 8 | Parallel reasoning with claims | 2-3h | ~1.0-1.5s | Medium | ★★★ |
| 9 | Parallel provider LLM calls | 1-2h | 0-5s (degradation) | Medium | ★★ |
| 10 | Background cache warming | 4-6h | Predictive | High | ★ |

**Target after implementing #1-6 (highest ROI):**
- Cache hit: **~10ms**
- First-time with prefetch: **~1.5-2.0s** ✓
- First-time without prefetch: **~3.0-3.5s** (close to target)

**Target after implementing all:**
- Cache hit: **~10ms**
- First-time with prefetch: **~1.0-1.5s** ✓✓
- First-time without prefetch: **~2.5-3.0s**

---

## Key Measurements

| Metric | Current | Target | After #1-6 |
|--------|---------|--------|------------|
| Cache hit response | N/A | <100ms | ~10ms |
| First-time (prefetch) | ~20s | <2s | ~1.5-2s |
| First-time (no prefetch) | ~20s | <2s | ~3-3.5s |
| LLM calls per analysis | 3 | 1-2 | 2 |
| yt-dlp calls | 2 | 0 | 0 |

---

## Architectural Changes Summary

| Component | Change |
|-----------|--------|
| `extension/content.js` | Add prefetch on Short navigation, send prefetched data with verify request |
| `extension/background.js` | Handle new message types for prefetch |
| `app/api/routes.py` | Accept `prefetched_transcript`, `prefetched_metadata` in request; add dedup |
| `app/services/transcript_service.py` | Remove Whisper fallback, accept pre-fetched transcript |
| `app/services/claim_service.py` | Switch to merged claim+classification prompt, use fast model |
| `app/services/classifier_service.py` | Deprecate — merged into claim service |
| `app/services/reasoning_service.py` | Support parallel start with limited context, fast re-verify |
| `app/pipeline/orchestrator.py` | Restructure for merged phases + parallel reasoning |
| `app/pipeline/analyzer.py` | Add in-flight deduplication |
| `app/llm/client.py` | Add LLM response cache, parallel provider calls, model selection |
| `app/llm/prompts/claim_and_classify.txt` | New merged prompt |
| `app/config.py` | Add per-service model config, remove unused Whisper keys |
| `app/schemas/pipeline_models.py` | Minimal changes — models already support merged flow |