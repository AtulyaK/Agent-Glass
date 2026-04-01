# Agent Glass: Architectural Decisions & Trade-Offs

## 1. The Microservice Choice vs Monolith
**Decision:** We split the pipeline into highly separated Docker containers (`trace-gateway`, `router`, `agent`, `critic`, `embedder`, `evaluator`).
**Trade-Offs:**
*   *Pros:* Complete isolation of the naive Agent from the Critic. If the Agent executes arbitrary code or crashes, the Critic remains functional to evaluate the failure. The Embedder (which handles massive matrices) is isolated and can be scaled on GPU nodes via NVIDIA NIM independently.
*   *Cons:* Infrastructure complexity. Requires maintaining a 6-container `docker-compose.yaml` network. Increases latency due to HTTP overhead between intra-system calls instead of native Python function calls.
**Verdict:** Necessary. Sandbox isolation is paramount in an AI observability platform designed to handle malicious code.

## 2. Using LangGraph for the Agent Core
**Decision:** The Agent is built using LangChain's `LangGraph` framework rather than custom `while` loops.
**Trade-Offs:**
*   *Pros:* Explicit state management. We can define rigid graph nodes (`plan` -> `trace` -> `tool`), making it incredibly easy to "pause" execution and emit traces to the `trace-gateway` *before* the LLM actually touches the system.
*   *Cons:* LangGraph's abstraction obscures standard Python stack traces when the LLM hallucinates malformed JSON.
**Verdict:** Highly advantageous for injecting arbitrary safety checkpoints seamlessly in the core execution flow.

## 3. Asynchronous Critiquing
**Decision:** The `trace-gateway` returns HTTP 200 to the Agent immediately upon receiving a trace, pushing the actual Evaluation to a background `asyncio` task (`asyncio.create_task(_async_evaluate_trace)`).
**Trade-Offs:**
*   *Pros:* Fast Agent feedback loops. The system doesn't stall waiting for a heavy Critic LLM to grade every minor trace.
*   *Cons:* "Ghost Events". An Agent might proceed to execute an action *before* the slow Critic realizes it's malicious.
**Verdict:** A deliberate design choice favoring system throughput, but requires architectural changes (like synchronous locks) if we transition this from an *Observability* platform to a *Prevention/Firewall* platform.

## 4. Vector Database: NVIDIA NIM `nv-embed-v1`
**Decision:** We recently migrated to `nvidia/nv-embed-v1` and upgraded PostgreSQL's `pgvector` to `VECTOR(4096)`.
**Trade-Offs:**
*   *Pros:* Supports a massive 32k context window and extremely rich semantic depth compared to the standard 512-token / 1024-dimension models. Handles lengthy CyberSecEval prompts gracefully.
*   *Cons:* 4096-dimensional vectors are huge. A 5M sample dataset will consume ~80GB of raw vector storage in Postgres. Requires robust indices (`HNSW` or `IVFFlat`) to search efficiently.

## 5. UMAP Processing Backend vs Frontend
**Decision:** We compute the UMAP 3-D dimensionality reduction in Python (`trace-gateway` endpoint) rather than in the browser using JS libraries.
**Trade-Offs:**
*   *Pros:* Python's `umap-learn` and `scikit-learn` are heavily optimized via C/C++. Avoids freezing the user's browser processing hundreds of 4096-dim arrays.
*   *Cons:* Requires the dashboard to continually poll the backend for updated coordinates if new data streams in dynamically.
