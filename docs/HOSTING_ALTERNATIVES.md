# Hosting LightOnOCR-2-1B — Alternative Approaches

## The Problem

Hugging Face now requires a **paid PRO subscription** (~$9/mo) to create Gradio or Docker Spaces. Free-tier accounts can only create Static Spaces (HTML/CSS only, no Python backend). The existing `HOSTING_PLAN.md` approach of running the model on HF Spaces is blocked without PRO.

## Option 1: Get HF PRO

- Upgrade to HF Pro → I set up a Gradio Space with `t4-small` GPU
- Permanent HTTPS endpoint, free inference within Space limits
- Cost: ~$9/mo + GPU compute (~$0.40/hr for T4 small)

## Option 2: Modal (Recommended for Free Tier)

- Serverless GPU platform with a generous free tier ($30/mo credit)
- Deploy a FastAPI app that loads `lightonai/LightOnOCR-2-1B`
- Permanent HTTPS endpoint, pay-per-use (idle costs $0)
- Cleanest developer experience — `modal deploy` and done

## Option 3: HF Inference API (Direct)

- If the model supports serverless inference, ClearLens calls `api-inference.huggingface.co/models/lightonai/LightOnOCR-2-1B` directly with your HF token
- No hosting needed — zero maintenance
- Requires the model to be compatible with HF's inference infrastructure

## Decision

Choose one and I'll set it up.