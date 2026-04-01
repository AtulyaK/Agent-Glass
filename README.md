# Agent Glass: AI Observability & Sentinel Pipeline

**Agent Glass** is a robust, production-ready framework for evaluating, observing, and sandboxing autonomous LLM agents. Designed scientifically to test LLMs against advanced adversarial threats, it proxies all LLM decisions through an asynchronous **AI Critic** and generates interactive 4096-dimensional 3D UMAP clusters to map the latent space of agent failure.

---

## 🚀 Quickstart: Zero to Hero

If you have never touched this repository, follow these steps to get a live 3D evaluation dashboard running locally.

### 1. Prerequisites
- **Docker & Docker Compose** installed.
- **Python 3.11+** installed locally (for fetching datasets).
- An active **NVIDIA NIM API Key**.

### 2. Environment Setup
Clone the repository and prepare your environment secrets:
```bash
cp .env.example .env
```
Open `.env` and paste your NVIDIA API token:
```ini
NVIDIA_API_KEY=nvapi-...
# Make sure NVIDIA_EMBED_MODEL=nvidia/nv-embed-v1 
# Make sure NVIDIA_HEAVY_MODEL=meta/llama-3.1-70b-instruct
```

### 3. Booting the Infrastructure
We utilize a 6-container microservice monorepo structure. Bring up PostgreSQL and the Python backend services:
```bash
cd infra/
docker compose --env-file ../.env up --build -d
```
*It may take a minute or two to download the images on the first run.*

### 4. Populating the Datasets (Optional but Recommended)
To scientifically test the Agent, you need to populate it with adversarial (Malicious) and benign (GAIA) prompts.
Open a new terminal at the project root:
```bash
# Create a local virtual environment
python3 -m venv venv
source venv/bin/activate
pip install -r services/evaluator/requirements.txt datasets pandas

# 1. Download and combine the tests (GAIA + HuggingFace Adversarial)
python scripts/build_dataset.py

# 2. Trickle these datasets into the Database to calculate Vector Embeddings!
# (This script automatically bypasses NVIDIA free-tier Rate Limits using Exponential Backoff)
python scripts/batch_embedder.py --limit 150
```

---

## 🎮 Running an Evaluation

Once the system is spun up and datasets exist, it's time to run an evaluation.
The **Evaluator** service forces the raw Agent to attempt the adversarial prompts, passing the resulting traces through the **Critic**.

Send a POST request to kick off an evaluation block (running 5 samples):
```bash
curl -X POST http://localhost:8006/run \
  -H 'content-type: application/json' \
  -d '{"limit": 5}'
```
*You can also specify a specific dataset source by passing `"source": "malicious"` or `"source": "gaia"` in the JSON payload.*

---

## 📊 The 3D UMAP Dashboard

The flagship feature of Agent Glass is its real-time Trace Visualization Dashboard.

Open your browser and navigate to:
👉 **[http://localhost:8001](http://localhost:8001)**

### Understanding the UI:
- **The Event Stream:** You will see Server-Sent Events (SSE) pouring in on the left side. These are the explicit thoughts (`trace_plan`) and actions (`trace_tool`) the LLM attempted to execute.
- **Threat Flags:** The Critic independently grades every action asynchronously:
  - 🟢 **Green:** Safe/Benign action.
  - 🟡 **Yellow:** Roadblock or loop detected (system intervention required).
  - 🔴 **Red:** Malicious payload execution blocked.
- **The 3D UMAP Cluster:** On the right, Plotly.js renders a 3-Dimensional representation of the 4096-dimensional vectors created from the Agent's traces. 
  - Over time, you can visually observe distinct grouping patterns between GAIA (benign logic tests) and Adversarial (prompt injections, jailbreaks) clusters!

---

## 🏗 System Architecture

Agent Glass is modular and built to scale:
- `trace-gateway`: The central nervous system. Ingests all LangGraph traces, stores them in Postgres, triggers the Critic, and broadcasts SSEs.
- `critic`: The safety gatekeeper evaluating payloads via structured JSON logic and loop detection.
- `evaluator` & `synthetic-gen`: The scientific testing arms.
- `embedder`: Generates `VECTOR(4096)` mathematical semantics using NIM for UMAP plotting.
- `agent`: The naive LLM execution proxy built using standard LangChain nodes.

Detailed architectural diagrams, trade-off analyses, and future roadmap files are located in `docs/architecture/`.
