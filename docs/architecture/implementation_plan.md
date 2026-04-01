# Phase 6: Robust Batch Embedding System

## Goal Description
The NVIDIA NIM integration for `nv-embedqa-e5-v5` is failing for two reasons:
1. **Token Limits**: Prompts exceeding 512 tokens crash the embedder with a 400 Bad Request.
2. **Rate Limits**: Free-tier NVIDIA NIM accounts throw 429 Too Many Requests when hitting it concurrently or too fast.

The goal is to fix the 512-token limit natively in the embedder service and create a robust background script that can safely trickle-embed our massive datasets without breaking rate limits.

## Architecture & Proposed Changes

### 1. Fix Token Limit in Embedder
We will modify the `embedder` service to tell NVIDIA to automatically truncate inputs instead of crashing.

#### [MODIFY] `services/embedder/app/main.py`
Add `"truncate": "END"` alongside `"input_type": "query"` in the `extra_body` payload of the OpenAI client call.

### 2. Batch Ingestion System
We will create a standalone python worker script that processes our `.jsonl` datasets and feeds them to the database while respecting API rate limits.

#### [NEW] `scripts/batch_embedder.py`
A Python script that:
1. Loads items from `data/train.jsonl` (or test/val).
2. Checks the database to see if the `sample_id` has already been embedded (idempotency).
3. If not, it requests `POST /embed` from the embedder.
4. **Rate Limit Handling**: If a 429 is received, it uses exponential backoff (e.g. sleeps 5s, 10s, 20s) before retrying.
5. Injects the resulting traces, events, and embeddings directly into PostgreSQL.

## Verification Plan

1.  **Dependencies**: No new docker dependencies required.
2.  **API Check**: Trigger the embedder with a massively long 1000-word prompt to ensure `"truncate": "END"` intercepts the 400 error. Check the Docker logs for successful 200 OK.
3.  **Batch Script Check**: Run `python scripts/batch_embedder.py --limit 1000` and verify it successfully delays and trickles requests into the database over several minutes without crashing.
