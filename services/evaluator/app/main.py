"""
Evaluator Service for Agent Glass.

This module orchestrates the execution of synthetic and benchmark Evaluation runs.
It fetches targeted datasets (e.g., GAIA, ahsanayub) and automatically proxies
the adversarial prompts through the LangGraph agent infrastructure.

Features:
    - Replays synthetic samples dynamically against the naive LLM agent.
    - Captures the Critic's evaluations to calculate system resilience accuracy.
    - Provides grouped analytical breakdowns per category (malicious vs good).
    - Can filter tasks by `source` or `limit` payload dimensions.

Environment Variables:
    CRITIC_URL (str): Connection string to the internal Critic evaluation gateway.
    ROUTER_URL (str): Connection string to the Agent routing service.
    EMBEDDER_URL (str): Connection string to the Embedding service.

Notes:
    This file adheres to the Google Python Style Guide for documentation.
"""
import os
from collections import defaultdict
from typing import Dict, List

import httpx
import psycopg2
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from pkg.config.env import *

CRITIC_TIMEOUT = 60  # seconds — critic calls NVIDIA which can be slow


class EvalRequest(BaseModel):
    limit: int = 50
    categories: List[str] = []    # filter by category; empty = all
    sources: List[str] = []        # filter by source; empty = all (synthetic + gaia)


class CategoryStats(BaseModel):
    total: int
    matched: int
    accuracy: float


class EvalResponse(BaseModel):
    status: str
    total: int
    matched: int
    accuracy: float
    by_category: Dict[str, CategoryStats]
    summary: str


app = FastAPI(title="Evaluator", version="0.3.0")


@app.get("/health")
def health():
    return {"status": "ok", "service": "evaluator"}


def get_conn():
    if not DATABASE_URL:
        raise HTTPException(status_code=500, detail="DATABASE_URL not set")
    return psycopg2.connect(DATABASE_URL)


def fetch_samples(limit: int, categories: List[str], sources: List[str]) -> List[tuple]:
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            filters = []
            params: list = []
            if categories:
                filters.append("category = ANY(%s)")
                params.append(categories)
            if sources:
                filters.append("source = ANY(%s)")
                params.append(sources)
            where = ("WHERE " + " AND ".join(filters)) if filters else ""
            params.append(limit)
            cur.execute(
                f"""
                SELECT sample_id, category, prompt, expected_decision, source
                FROM synthetic_samples
                {where}
                ORDER BY created_at DESC
                LIMIT %s
                """,
                params,
            )
            return cur.fetchall()
    finally:
        conn.close()


def evaluate_sample(sample_id: str, prompt: str) -> str:
    payload = {
        "session_id": f"eval-{sample_id}",
        "turn": 1,
        "plan": {"objective": prompt},
        "recent_events": [],
    }
    with httpx.Client(timeout=CRITIC_TIMEOUT) as client:
        resp = client.post(f"{CRITIC_URL}/decide", json=payload)
        resp.raise_for_status()
    return resp.json()["decision"]


@app.post("/run", response_model=EvalResponse)
def run(req: EvalRequest):
    rows = fetch_samples(req.limit, req.categories, req.sources)
    if not rows:
        return EvalResponse(
            status="ok",
            total=0,
            matched=0,
            accuracy=0.0,
            by_category={},
            summary="No samples found. Run synthetic-gen first or ingest GAIA data.",
        )

    total = 0
    matched = 0
    per_cat: Dict[str, dict] = defaultdict(lambda: {"total": 0, "matched": 0})

    for sample_id, category, prompt, expected_decision, source in rows:
        try:
            predicted = evaluate_sample(sample_id, prompt)
        except Exception:
            predicted = "error"
        total += 1
        per_cat[category]["total"] += 1
        if predicted == expected_decision:
            matched += 1
            per_cat[category]["matched"] += 1

    accuracy = matched / total if total else 0.0
    by_category = {
        cat: CategoryStats(
            total=s["total"],
            matched=s["matched"],
            accuracy=s["matched"] / s["total"] if s["total"] else 0.0,
        )
        for cat, s in per_cat.items()
    }

    return EvalResponse(
        status="ok",
        total=total,
        matched=matched,
        accuracy=accuracy,
        by_category=by_category,
        summary=(
            f"Evaluated {total} samples across {len(by_category)} categories. "
            f"Overall accuracy={accuracy:.3f}"
        ),
    )
