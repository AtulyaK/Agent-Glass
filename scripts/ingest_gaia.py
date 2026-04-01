#!/usr/bin/env python3
"""
GAIA Benchmark Ingest Script
=============================
Downloads the GAIA validation split from Hugging Face and inserts tasks into
the synthetic_samples table with source='gaia'.

Requirements (run outside Docker):
    pip install datasets psycopg2-binary huggingface_hub

Usage:
    # Make sure docker compose is running (exposes Postgres on 5432)
    python scripts/ingest_gaia.py

    # Then run the evaluator to check critic accuracy on GAIA:
    curl -X POST http://localhost:8006/run -H 'content-type: application/json' \
         -d '{"limit":100, "sources":["gaia"]}'

Environment:
    DATABASE_URL  — defaults to localhost:5432 (host-side access)
    HF_TOKEN      — required if GAIA is gated on HuggingFace
"""
import os
import uuid
import json
import psycopg2
import psycopg2.extras

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/agent_glass",
)
HF_TOKEN = os.getenv("HF_TOKEN")

# GAIA's task levels map to our safety categories approximately:
LEVEL_TO_CATEGORY = {
    1: "good",      # straightforward factual tasks → expect critic to approve
    2: "near_miss", # multi-step tasks → expect critic to approve with nuance
    3: "near_miss", # complex reasoning → edge case
}

# GAIA tasks are well-formed research tasks → expected critic decision is approve.
# For malicious/roadblock testing use inject-failure instead.
EXPECTED_DECISION = "approve"


def ingest(limit: int = 200) -> int:
    try:
        from datasets import load_dataset
    except ImportError:
        print("ERROR: Install 'datasets' package:  pip install datasets")
        return 0

    print(f"Downloading GAIA validation split (limit={limit})...")
    try:
        ds = load_dataset(
            "gaia-benchmark/GAIA",
            "2023_all",
            split="validation",
            token=HF_TOKEN,
        )
    except Exception as e:
        print(f"ERROR loading GAIA dataset: {e}")
        print("You may need to: (1) accept the GAIA license on HuggingFace and "
              "(2) set HF_TOKEN env var.")
        return 0

    conn = psycopg2.connect(DATABASE_URL)
    inserted = 0

    try:
        with conn:
            with conn.cursor() as cur:
                for i, row in enumerate(ds):
                    if i >= limit:
                        break
                    level = int(row.get("Level", 1))
                    question = row.get("Question", "").strip()
                    if not question:
                        continue

                    category = LEVEL_TO_CATEGORY.get(level, "good")
                    sample_id = str(uuid.uuid4())
                    metadata = {
                        "gaia_task_id": row.get("task_id", ""),
                        "level": level,
                        "final_answer": row.get("Final answer", ""),
                        "num_steps": len(row.get("Annotator Metadata", {}).get("Steps", [])),
                    }

                    cur.execute(
                        """
                        INSERT INTO synthetic_samples
                          (sample_id, source, category, prompt, expected_decision, metadata)
                        VALUES (%s, 'gaia', %s, %s, %s, %s)
                        ON CONFLICT (sample_id) DO NOTHING
                        """,
                        (
                            sample_id,
                            category,
                            question,
                            EXPECTED_DECISION,
                            psycopg2.extras.Json(metadata),
                        ),
                    )
                    inserted += cur.rowcount

    finally:
        conn.close()

    print(f"Inserted {inserted} GAIA tasks into synthetic_samples (source='gaia').")
    return inserted


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Ingest GAIA benchmark into agent_glass DB")
    parser.add_argument("--limit", type=int, default=200, help="Max tasks to ingest")
    args = parser.parse_args()
    ingest(limit=args.limit)
