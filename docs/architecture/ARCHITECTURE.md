# Agent Glass — Architecture

## Overview

Agent Glass is an LLM observability and safety evaluation platform. It runs a set of FastAPI microservices coordinated by Docker Compose, backed by Postgres with the `pgvector` extension for semantic search over trace embeddings.

All LLM inference is provider-only via **NVIDIA NIM** (`integrate.api.nvidia.com`). No local model weights are required.

---

## Service Map

```
                        ┌─────────────────┐
  User / Test Harness   │   8007/generate │  ← create synthetic eval samples
                        │  synthetic-gen  │
                        └────────┬────────┘
                                 │ SQL (direct)
                        ┌────────▼────────┐
                        │    Postgres     │  db:5432
                        │  + pgvector     │
                        └───┬────────┬───┘
                            │        │
              ┌─────────────▼─┐    ┌─▼──────────────┐
              │  trace-gateway│    │    embedder     │
              │ :8002/event   │───▶│ :8005/embed     │
              └───────────────┘    │       /embed-store│
                                   └─────────────────┘
                                           ▲
                        ┌──────────────────┤
                        │    critic        │  uses embedder for k-NN evidence
                        │ :8003/decide     │  then calls NVIDIA heavy model
                        └────────┬─────────┘
                                 ▲
              ┌──────────────────┤
              │    evaluator     │  replays synthetic_samples → critic
              │  :8006/run       │
              └──────────────────┘

              ┌──────────────────┐
              │     router       │  stateless model selection (NVIDIA only)
              │  :8001/route     │
              └────────┬─────────┘
                       ▲
              ┌────────┴─────────┐
              │     agent        │  calls router → calls NVIDIA
              │  :8004/plan      │
              └──────────────────┘

              ┌──────────────────┐
              │    frontend      │  static HTML placeholder
              │  :3000/          │
              └──────────────────┘
```

---

## Services

| Service | Port | Purpose | NVIDIA Model Used |
|---------|------|---------|-------------------|
| `router` | 8001 | Stateless model-selection policy | none (returns model name only) |
| `trace-gateway` | 8002 | Ingest trace events → DB + trigger embedding | none |
| `critic` | 8003 | Safety decision: approve / modify / deny | `NVIDIA_HEAVY_MODEL` |
| `agent` | 8004 | Generates multi-step plans, routed via `router` | `NVIDIA_HEAVY_MODEL` |
| `embedder` | 8005 | Text → vector embeddings → stored in pgvector | `NVIDIA_EMBED_MODEL` |
| `evaluator` | 8006 | Replays synthetic samples through critic, reports accuracy | none |
| `synthetic-gen` | 8007 | Generates labeled synthetic eval samples via LLM | `NVIDIA_HEAVY_MODEL` |
| `frontend` | 3000 | Static placeholder HTML | none |
| `db` | 5432 | Postgres + pgvector | — |

---

## Database Tables (inferred from queries)

| Table | Purpose |
|-------|---------|
| `sessions` | One row per session_id |
| `events` | Raw trace events (session, turn, node, event_type, payload, hashes) |
| `embeddings` | pgvector rows (session, event_id, label, provider, model, checksum, vector) |
| `critic_decisions` | One row per critic call (session, turn, decision, flag, rationale, halt) |
| `synthetic_samples` | LLM-generated eval rows (sample_id, source, category, prompt, expected_decision, metadata) |

---

## Environment Variables (`.env`)

| Variable | Default (code) | Description |
|----------|---------------|-------------|
| `NVIDIA_API_KEY` | *(required)* | NVIDIA NIM API key |
| `NVIDIA_BASE_URL` | `https://integrate.api.nvidia.com/v1` | NVIDIA NIM base URL |
| `NVIDIA_FAST_MODEL` | `nvidia/nemotron-mini-4b-instruct` | Fast-tier chat model |
| `NVIDIA_HEAVY_MODEL` | `meta/llama-3.1-70b-instruct` | Heavy-tier chat model (**must be `meta/` prefix**) |
| `NVIDIA_EMBED_MODEL` | `nvidia/nv-embedqa-e5-v5` | Embedding model |
| `DATABASE_URL` | — | Postgres connection string |

> **Important**: `NVIDIA_HEAVY_MODEL` and `NVIDIA_EMBED_MODEL` must be set explicitly in `.env`. The code fallbacks use incorrect values.

---

## Test Flow

```bash
# 1. Start everything
cd infra && docker compose --env-file ../.env up --build -d

# 2. Health checks
curl http://localhost:8001/health   # router
curl http://localhost:8002/health   # trace-gateway
curl http://localhost:8003/health   # critic
curl http://localhost:8007/health   # synthetic-gen

# 3. Generate synthetic samples
curl -X POST http://localhost:8007/generate \
  -H 'content-type: application/json' \
  -d '{"count":5}'

# 4. Run evaluator (requires samples to exist first)
curl -X POST http://localhost:8006/run \
  -H 'content-type: application/json' \
  -d '{"limit":5}'

# 5. Ingest a trace event manually
curl -X POST http://localhost:8002/event \
  -H 'content-type: application/json' \
  -d '{"session_id":"test-1","turn":1,"event_type":"tool_call","payload":{"tool":"search"}}'

# 6. Ask the critic for a decision
curl -X POST http://localhost:8003/decide \
  -H 'content-type: application/json' \
  -d '{"session_id":"test-1","turn":1,"plan":{"objective":"search the web"},"recent_events":[]}'
```

---

## Known Issues

See [implementation_plan.md] for the active bug fix: wrong NVIDIA model names causing 502 on `/generate`.
