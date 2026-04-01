# Codebase Recommendations: Towards Production

As the application approaches its final vision (a robust scientific evaluation suite for LLM agents), the codebase has accumulated some prototype debt. The following are actionable recommendations for updating, moving, or deleting components to tighten the system.

## 1. What to UPDATE

### Centralized Configuration Manager
Right now, `trace-gateway/app/main.py`, `embedder/app/main.py`, and `critic/app/main.py` all independently parse `os.getenv` strings and handle connection logic to PostgreSQL and NVIDIA APIs.
*   **Recommendation:** Abstract environment parsing and service registry configs (like `EMBEDDER_URL`) into a shared `pkg/config` common python module. This guarantees consistency across services.

### UMAP Memory Leak Fix
`trace-gateway` calculates UMAP dynamically on the `GET /visualization/umap` endpoint. Currently, this runs synchronously, blocking the FastAPI event loop for 1-3 seconds.
*   **Recommendation:** Wrap UMAP inside `asyncio.to_thread` or utilize `BackgroundTasks`. Additionally, UMAP results should be cached in Redis with a 5-minute TTL so multiple dashboard viewers don't thrash the server.

## 2. What to MOVE or ARRANGE

### Extract Evaluation Logic from `synthetic-gen`
Currently, `synthetic-gen` holds the data loaders for GAIA and adversarial tests. The `evaluator` runs scenarios.
*   **Recommendation:** Merge `synthetic-gen` and `evaluator` into a single `testing-suite` service container. They share the same dependency context (the prompt dataset) and having them split into two containers only increases compose build complexity.

### Restructure `frontend`
The `frontend` is currently served via simple HTML/JS. 
*   **Recommendation:** As the complexity of the WebSocket traces and standard HTTP states grows, managing DOM updates manually in `index.html` will become brittle. The UI should be ported to React (Next.js) with proper state management tools (Zustand or Redux) to handle the firehose of `/stream` events seamlessly.

## 3. What to DELETE

### Deprecated Stub Services
In early iterations, there were fallback manual stubs used when the LLMs API was unavailable. Now that the NIM models are robustly locked in (`NVIDIA_HEAVY_MODEL`, `NVIDIA_EMBED_MODEL`), any mock interfaces or dummy prompt generators should be scrubbed from the `agent` library to reduce file bloat.

### Stale Vector Data Migrations
The database schema (`02-tables.sql`) currently requires manual teardown to alter dimensions.
*   **Recommendation:** Delete raw SQL initialization files and replace them with an `alembic` based python migration framework for SQLAlchemy. This will allow seamless, programmatic transitions if we switch embedding models again without raw `TRUNCATE TABLE` commands.
