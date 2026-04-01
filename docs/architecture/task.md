# Task: Implement All Roadmap Phases

## Phase 1: LangGraph Agent ✅
- [x] Add langgraph to agent/requirements.txt
- [x] Fix DB schema: vector(1024), threat_class, human_note
- [x] Write LangGraph graph (plan→trace_plan→simulate_tool→trace_tool)
- [x] Verify /health shows graph nodes
- [x] Verify /plan returns structured steps
- [x] Verify traces stored in trace-gateway

## Phase 2: Smarter Critic ✅
- [x] Structured JSON system prompt (approve/modify/deny + threat_class)
- [x] Robust JSON response parser (handles markdown fences)
- [x] Loop detection pre-check (queries last N decisions)
- [x] Store threat_class to DB
- [x] /feedback endpoint (human-in-the-loop)
- [x] Test critic with malicious / roadblock / good samples

## Phase 3: Evaluation Pipeline ✅
- [x] GAIA ingest script
- [x] Per-category accuracy breakdown in evaluator
- [x] Failure injection endpoint in synthetic-gen

## Phase 4: Frontend Dashboard ✅
- [x] SSE stream from trace-gateway
- [x] Replace frontend stub (Next.js or rich HTML)
- [x] Real-time session list with green/yellow/red flags
- [x] Human feedback UI

## Phase 5: Scientific Evaluation Dataset
- [x] Build unified dataset script (GAIA, ahsanayub, codesagar) with train/test/val splits
- [ ] Build ingestion pipeline for Meta CyberSecEval attacks
- [ ] Develop adversarial LLM-as-a-red-team generator
- [x] Implement UMAP 2D/3D visualization of trace embeddings in Dashboard

## Phase 6: Robust Batch Embedding System
- [x] Verify API models and upgrade defaults to `nv-embed-v1` (32k max tokens, 4096 dim)
- [x] Update database schema to `VECTOR(4096)`
- [x] Build rate-limiting exponential backoff ingest script `batch_embedder.py`

## Phase 7: Codebase Productionization
- [x] DB Optimization: Embedder checksum caching (prevent duplicate NVIDIA NIM calls)
- [x] Architecture: Centralize environment config into a shared `pkg/config`
- [ ] Architecture: Merge `synthetic-gen` and `evaluator` into `testing-suite`
- [x] Performance: Fix UMAP memory thread blocking with Redis/LRU caching
- [x] Documentation: Organize artifacts into `docs/` and generate granular file-level docs
- [x] Cleanup: Ensure Google Python Style Guide compliance and remove stale code

## Phase 9: Hugging Face Dataset Deployment
- [x] Research: Hugging Face Hub limits and streaming upload methods
- [x] Implementation: Create `scripts/push_to_hf.py` for direct streaming/upload
- [x] Optimization: Update `build_dataset.py` to optionally bypass local disk
- [x] Verification: Verify dataset `akane69/Agent-Glass` is accessible and correctly formatted

## Phase 1: Research & Diagnosis
- [x] Read README and understand project layout
- [x] Read compose.yaml
- [x] Read .env and .env.example
- [x] Read synthetic-gen/app/main.py
- [x] Read router/app/main.py
- [x] Read embedder/app/main.py
- [x] Read evaluator/app/main.py
- [x] Research correct NVIDIA NIM model names

## Phase 2: Planning
- [x] Create implementation_plan.md
- [x] Create codebase documentation (ARCHITECTURE.md)
- [x] Get user approval

## Phase 3: Execution
- [x] Fix model names in .env (added NVIDIA_FAST_MODEL, NVIDIA_HEAVY_MODEL, NVIDIA_EMBED_MODEL)
- [x] Fix hardcoded defaults in synthetic-gen, critic, agent → meta/llama-3.1-70b-instruct
- [x] Fix embedder default → nvidia/nv-embedqa-e5-v5

## Phase 4: Verification
- [x] Rebuild Docker containers
- [x] Verify /generate works without 502
