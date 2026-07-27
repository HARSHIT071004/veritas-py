#!/usr/bin/env python3
"""
ClearLens End-to-End Pipeline Test Script

Usage:
    python scripts/test_pipeline.py [--url VIDEO_URL]

If no URL is provided, a default Hindi Shorts video is used.
"""

import asyncio
import json
import logging
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("clearlens.e2e")

CHECK_MARK = "PASS"
FAIL_MARK = "FAIL"
SKIP_MARK = "SKIP"

results = []
stage_timings = {}


def record(stage: str, status: str, detail: str = ""):
    mark = CHECK_MARK if status == "pass" else (FAIL_MARK if status == "fail" else SKIP_MARK)
    results.append({"stage": stage, "status": status, "detail": detail})
    logger.info(f"  [{mark}] {stage}" + (f" — {detail}" if detail else ""))


def check_redis() -> bool:
    try:
        import redis
        r = redis.Redis.from_url("redis://localhost:6379", socket_connect_timeout=2)
        r.ping()
        r.close()
        record("Redis check", "pass", "Redis is running on localhost:6379")
        return True
    except Exception as e:
        record("Redis check", "skip", f"Redis unavailable: {e}")
        return False


def check_ytdlp() -> bool:
    try:
        import yt_dlp
        record("yt-dlp check", "pass", f"yt-dlp {yt_dlp.version.__version__} available")
        return True
    except Exception as e:
        record("yt-dlp check", "fail", f"yt-dlp not installed: {e}")
        return False


def download_video(video_url: str, output_dir: Path) -> Optional[dict]:
    import yt_dlp

    logger.info(f"Downloading video metadata: {video_url}")
    t0 = time.time()
    try:
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "extract_flat": False,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)

        duration = info.get("duration", 0)
        stage_timings["download"] = int((time.time() - t0) * 1000)

        video_id = info.get("id", "unknown")
        title = info.get("title", "")
        channel = info.get("channel", info.get("uploader", ""))
        description = info.get("description", "")

        metadata = {
            "video_id": video_id,
            "title": title,
            "channel": channel,
            "description": description[:2000],
            "duration": duration,
            "url": video_url,
            "hashtags": [t.get("name", "") for t in info.get("tags", []) if isinstance(t, dict)] if info.get("tags") else [t for t in info.get("tags", []) if isinstance(t, str)],
        }

        metadata_file = output_dir / "video_metadata.json"
        with open(metadata_file, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        record("Download video", "pass", f"'{title}' ({duration}s) -> {metadata_file}")
        return metadata

    except Exception as e:
        stage_timings["download"] = int((time.time() - t0) * 1000)
        record("Download video", "fail", str(e))
        return None


async def run_transcript(video_id: str, output_dir: Path) -> Optional[str]:
    t0 = time.time()
    try:
        from app.services.transcript_service import TranscriptService
        svc = TranscriptService()
        result = await svc.extract(video_id)

        transcript_text = result.text if hasattr(result, "text") else (result.get("transcript") if isinstance(result, dict) else "")
        source = result.source if hasattr(result, "source") else (result.get("source") if isinstance(result, dict) else "unknown")

        stage_timings["transcript"] = int((time.time() - t0) * 1000)

        transcript_file = output_dir / "transcript.txt"
        with open(transcript_file, "w", encoding="utf-8") as f:
            f.write(transcript_text or "")

        if transcript_text:
            record("Transcript extraction", "pass", f"source={source}, length={len(transcript_text)} chars")
        else:
            record("Transcript extraction", "skip", "empty transcript")
        return transcript_text

    except Exception as e:
        stage_timings["transcript"] = int((time.time() - t0) * 1000)
        record("Transcript extraction", "fail", str(e))
        return None


async def run_claim_extraction(transcript: str, title: str, description: str, channel: str, output_dir: Path) -> Optional[list]:
    t0 = time.time()
    try:
        from app.services.claim_service import ClaimService
        svc = ClaimService()
        result = await svc.extract(transcript=transcript or "", ocr_text="", title=title, description=description, channel=channel)

        stage_timings["claims"] = int((time.time() - t0) * 1000)

        claims = []
        if hasattr(result, "claims") and result.claims:
            claims = [{"claim": c.claim, "category": getattr(c, "category", ""), "confidence": getattr(c, "confidence", 0.0)} for c in result.claims]
        elif isinstance(result, dict):
            claims = result.get("claims", [])

        claims_file = output_dir / "claims.json"
        with open(claims_file, "w", encoding="utf-8") as f:
            json.dump(claims, f, indent=2, ensure_ascii=False)

        record("Claim extraction", "pass" if claims else "skip", f"{len(claims)} claims extracted")
        return claims

    except Exception as e:
        stage_timings["claims"] = int((time.time() - t0) * 1000)
        record("Claim extraction", "fail", str(e))
        return None


async def run_classification(claims: list, output_dir: Path) -> Optional[list]:
    if not claims:
        record("Classification", "skip", "no claims to classify")
        return []

    t0 = time.time()
    try:
        from app.services.classifier_service import ClassifierService
        svc = ClassifierService()
        claim_texts = [c["claim"] if isinstance(c, dict) else c for c in claims]
        result = await svc.classify(claim_texts)

        stage_timings["classification"] = int((time.time() - t0) * 1000)

        classifications = []
        if hasattr(result, "classifications"):
            classifications = [{"category": c.category, "confidence": c.confidence} for c in result.classifications]
        elif isinstance(result, dict):
            classifications = result.get("classifications", [])

        class_file = output_dir / "classification.json"
        with open(class_file, "w", encoding="utf-8") as f:
            json.dump(classifications, f, indent=2, ensure_ascii=False)

        record("Classification", "pass" if classifications else "skip", f"{len(classifications)} classified")
        return classifications

    except Exception as e:
        stage_timings["classification"] = int((time.time() - t0) * 1000)
        record("Classification", "fail", str(e))
        return None


async def run_reasoning(claims_text: str, transcript: str, output_dir: Path) -> Optional[dict]:
    t0 = time.time()
    try:
        from app.services.reasoning_service import ReasoningService
        svc = ReasoningService()
        result = await svc.analyze(claim=claims_text, claim_category="general", transcript=transcript or "", ocr_text="", evidence=[])

        stage_timings["reasoning"] = int((time.time() - t0) * 1000)

        reasoning = {}
        if hasattr(result, "verdict"):
            reasoning = {
                "claim": getattr(result, "claim", ""),
                "verdict": result.verdict,
                "confidence": getattr(result, "confidence", 0.0),
                "explanation": getattr(result, "explanation", ""),
                "risk_level": getattr(result, "risk_level", "unknown"),
                "key_factors": getattr(result, "key_factors", []),
                "sources": getattr(result, "sources", []),
            }
        elif isinstance(result, dict):
            reasoning = result

        reasoning_file = output_dir / "reasoning.json"
        with open(reasoning_file, "w", encoding="utf-8") as f:
            json.dump(reasoning, f, indent=2, ensure_ascii=False)

        record("Reasoning", "pass" if reasoning.get("verdict") else "skip", f"verdict={reasoning.get('verdict', 'N/A')}")
        return reasoning

    except Exception as e:
        stage_timings["reasoning"] = int((time.time() - t0) * 1000)
        record("Reasoning", "fail", str(e))
        return None


def run_trust(verdict: str, confidence: float, sources: list, output_dir: Path) -> Optional[dict]:
    t0 = time.time()
    try:
        from app.services.trust_service import TrustService
        svc = TrustService()
        evidence_sources = [{"source_tier": 1, "contradicts": False}] if sources else []
        score = svc.calculate(verdict=verdict, llm_confidence=confidence, evidence_sources=evidence_sources, evidence_count=len(sources))

        stage_timings["trust"] = int((time.time() - t0) * 1000)

        trust = {"score": score.score, "label": score.label, "evidence_coverage": score.evidence_coverage, "llm_confidence_component": score.llm_confidence_component, "source_tier_component": score.source_tier_component}

        trust_file = output_dir / "trust_score.json"
        with open(trust_file, "w", encoding="utf-8") as f:
            json.dump(trust, f, indent=2, ensure_ascii=False)

        record("Trust score", "pass", f"score={score.score:.2f}, label={score.label}")
        return trust

    except Exception as e:
        stage_timings["trust"] = int((time.time() - t0) * 1000)
        record("Trust score", "fail", str(e))
        return None


def save_pipeline_result(output_dir: Path, metadata: dict, transcript: str, claims: list, classifications: list, reasoning: dict, trust: dict, job_id: str):
    result = {
        "pipeline_version": "1.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "job_id": job_id,
        "video": metadata,
        "transcript": {"length": len(transcript or ""), "preview": (transcript or "")[:500]},
        "claims": claims or [],
        "classifications": classifications or [],
        "reasoning": reasoning or {},
        "trust_score": trust or {},
        "timings": stage_timings,
        "total_duration_ms": sum(stage_timings.values()),
    }

    result_file = output_dir / "pipeline_result.json"
    with open(result_file, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    record("Save pipeline result", "pass", str(result_file))
    return result


def validate(result: dict) -> bool:
    all_pass = True

    if result.get("transcript", {}).get("length", 0) > 0:
        record("Validation: transcript not empty", "pass", f"{result['transcript']['length']} chars")
    else:
        record("Validation: transcript not empty", "fail", "transcript is empty")
        all_pass = False

    claims = result.get("claims", [])
    if len(claims) > 0:
        record("Validation: claims extracted", "pass", f"{len(claims)} claims")
    else:
        record("Validation: claims extracted", "fail", "no claims extracted")
        all_pass = False

    classifications = result.get("classifications", [])
    if len(classifications) > 0:
        record("Validation: classification completed", "pass", f"{len(classifications)} items")
    else:
        record("Validation: classification completed", "fail", "classification empty")
        all_pass = False

    reasoning = result.get("reasoning", {})
    if reasoning.get("verdict"):
        record("Validation: reasoning completed", "pass", f"verdict={reasoning['verdict']}")
    else:
        record("Validation: reasoning completed", "fail", "no verdict")
        all_pass = False

    trust = result.get("trust_score", {})
    if trust.get("score", 0) >= 0:
        record("Validation: trust score generated", "pass", f"score={trust['score']:.2f}")
    else:
        record("Validation: trust score generated", "fail", "invalid trust score")
        all_pass = False

    required_files = ["video_metadata.json", "claims.json", "classification.json", "reasoning.json", "trust_score.json", "pipeline_result.json"]
    output_dir = Path(result.get("_output_dir", ""))
    if output_dir.exists():
        missing = [f for f in required_files if not (output_dir / f).exists()]
        if missing:
            record("Validation: files on disk", "fail", f"missing: {', '.join(missing)}")
            all_pass = False
        else:
            record("Validation: files on disk", "pass", f"{len(required_files)} files in {output_dir}")

    return all_pass


def print_summary(result: dict):
    print()
    print("=" * 70)
    print("  ClearLens — Pipeline Summary")
    print("=" * 70)
    print(f"  Video URL:     {result.get('video', {}).get('url', 'N/A')}")
    print(f"  Title:         {result.get('video', {}).get('title', 'N/A')}")
    print(f"  Channel:       {result.get('video', {}).get('channel', 'N/A')}")
    print(f"  Duration:      {result.get('video', {}).get('duration', 'N/A')}s")
    print(f"  Job ID:        {result.get('job_id', 'N/A')}")
    print(f"  Total time:    {result.get('total_duration_ms', 0)}ms")
    print()
    print(f"  Transcript:    {result.get('transcript', {}).get('length', 0)} chars from {result.get('transcript_preview', {}).get('source', 'N/A')}")
    print(f"  Claims:        {len(result.get('claims', []))}")
    print(f"  Verdict:       {result.get('reasoning', {}).get('verdict', 'N/A')}")
    print(f"  Confidence:    {result.get('reasoning', {}).get('confidence', 0.0):.2f}")
    print(f"  Trust score:   {result.get('trust_score', {}).get('score', 0.0):.2f} ({result.get('trust_score', {}).get('label', 'N/A')})")
    print(f"  Cache:         miss")
    print()
    print("  Stage Timings:")
    for stage, ms in sorted(result.get("timings", {}).items()):
        print(f"    {stage:20s} {ms:>6}ms")
    print()
    print("  Validation:")

    passed = sum(1 for r in results if r["status"] == "pass")
    failed = sum(1 for r in results if r["status"] == "fail")
    skipped = sum(1 for r in results if r["status"] == "skip")

    for r in results:
        mark = CHECK_MARK if r["status"] == "pass" else (FAIL_MARK if r["status"] == "fail" else SKIP_MARK)
        print(f"    [{mark}] {r['stage']}" + (f" — {r['detail']}" if r.get("detail") else ""))

    print()
    print(f"  Result: {CHECK_MARK if failed == 0 else FAIL_MARK}")
    print(f"  Passed: {passed}  Failed: {failed}  Skipped: {skipped}")
    print("=" * 70)

    return failed == 0


async def main():
    default_url = "https://www.youtube.com/shorts/6AHpWl75e8M"

    if len(sys.argv) > 1:
        video_url = sys.argv[1]
    else:
        video_url = default_url
        logger.info(f"No URL provided, using default: {default_url}")

    print()
    print("=" * 70)
    print("  ClearLens — End-to-End Pipeline Test")
    print("=" * 70)
    print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Video:   {video_url}")
    print("=" * 70)
    print()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path("outputs") / timestamp
    output_dir.mkdir(parents=True, exist_ok=True)
    record("Output directory", "pass", str(output_dir))

    file_handler = logging.FileHandler(output_dir / "pipeline.log", encoding="utf-8")
    file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
    logging.getLogger().addHandler(file_handler)

    redis_avail = check_redis()

    if not check_ytdlp():
        sys.exit(1)

    logger.info("Step 2: Downloading video")
    metadata = download_video(video_url, output_dir)
    if not metadata:
        record("Pipeline", "fail", "no video metadata — cannot continue")
        print_summary({"job_id": "N/A", "video": {}, "transcript": {}, "claims": [], "classifications": [], "reasoning": {}, "trust_score": {}, "timings": stage_timings, "_output_dir": str(output_dir)})
        sys.exit(1)

    job_id = uuid.uuid4().hex[:12]
    video_id = metadata["video_id"]
    title = metadata.get("title", "")
    description = metadata.get("description", "")
    channel = metadata.get("channel", "")

    logger.info("Step 3: Running pipeline")
    transcript = await run_transcript(video_id, output_dir)
    claims = await run_claim_extraction(transcript or "", title, description, channel, output_dir)
    classifications = await run_classification(claims or [], output_dir)
    claim_texts = " | ".join(c["claim"] for c in (claims or [])) if claims else (title or video_id)
    reasoning = await run_reasoning(claim_texts, transcript or "", output_dir)
    trust = run_trust(reasoning.get("verdict", "unverifiable") if reasoning else "unverifiable", reasoning.get("confidence", 0.0) if reasoning else 0.0, reasoning.get("sources", []) if reasoning else [], output_dir)

    logger.info("Step 4: Saving results")
    result = save_pipeline_result(output_dir, metadata, transcript, claims or [], classifications or [], reasoning or {}, trust or {}, job_id)
    result["_output_dir"] = str(output_dir)

    logger.info("Step 5: Validation")
    validate(result)

    logger.info("Step 6: Summary")
    success = print_summary(result)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
