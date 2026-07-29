import asyncio
import logging
from app.services.claim_service import ClaimService
from app.services.classifier_service import ClassifierService
from app.services.reasoning_service import ReasoningService
from app.evaluation.dataset import SAMPLE_CLAIMS

logger = logging.getLogger("clearlens.evaluation")


async def evaluate_claims():
    results = {"total": 0, "success": 0, "failed": 0, "details": []}
    classifier = ClassifierService()
    claim_svc = ClaimService()

    for i, claim_text in enumerate(SAMPLE_CLAIMS):
        results["total"] += 1
        try:
            class_res = await classifier.classify([claim_text])
            class_item = class_res.classifications[0] if class_res.classifications else None
            results["success"] += 1
            results["details"].append({
                "index": i,
                "claim": claim_text[:60],
                "category": class_item.category if class_item else "unknown",
                "confidence": class_item.confidence if class_item else 0,
            })
        except Exception as e:
            results["failed"] += 1
            results["details"].append({"index": i, "claim": claim_text[:60], "error": str(e)})

    return results


def print_report(results: dict):
    print(f"\n=== Evaluation Report ===")
    print(f"Total: {results['total']}")
    print(f"Success: {results['success']}")
    print(f"Failed: {results['failed']}")
    print(f"Success Rate: {results['success']/max(results['total'],1)*100:.1f}%")
    print(f"\nPer-claim results:")
    for d in results["details"]:
        status = "OK" if "error" not in d else "FAIL"
        cat = d.get("category", "?")
        conf = d.get("confidence", 0)
        print(f"  [{status}] {d['claim'][:50]:50s} → {cat:12s} ({conf:.2f})")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    results = asyncio.run(evaluate_claims())
    print_report(results)
