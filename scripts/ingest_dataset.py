#!/usr/bin/env python3
"""
JSONL Dataset Ingestion Script
==============================
Reads a unified JSONL file (e.g., data/val.jsonl) and inserts tasks into
the `synthetic_samples` database table.

Requirements:
    pip install psycopg2-binary

Usage:
    python scripts/ingest_dataset.py --file data/val.jsonl --limit 500
"""

import os
import json
import argparse
import psycopg2
import psycopg2.extras

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/agent_glass",
)

def ingest_file(filepath: str, limit: int = 500) -> int:
    if not os.path.exists(filepath):
        print(f"ERROR: File '{filepath}' not found.")
        return 0

    print(f"Connecting to DB and loading up to {limit} samples from {filepath}...")
    conn = psycopg2.connect(DATABASE_URL)
    inserted = 0

    try:
        with conn:
            with conn.cursor() as cur:
                with open(filepath, 'r', encoding='utf-8') as f:
                    for i, line in enumerate(f):
                        if i >= limit:
                            break
                            
                        row = json.loads(line)
                        
                        # Extract exact schema fields
                        sample_id = row["sample_id"]
                        source = row["source"]
                        category = row["category"]
                        expected_decision = row.get("expected_decision", "approve")
                        prompt = row["prompt"]
                        metadata = row.get("metadata", {})

                        cur.execute(
                            """
                            INSERT INTO synthetic_samples
                              (sample_id, source, category, prompt, expected_decision, metadata)
                            VALUES (%s, %s, %s, %s, %s, %s)
                            ON CONFLICT (sample_id) DO NOTHING
                            """,
                            (
                                sample_id,
                                source,
                                category,
                                prompt,
                                expected_decision,
                                psycopg2.extras.Json(metadata),
                            ),
                        )
                        inserted += cur.rowcount
    except Exception as e:
        print(f"Database error: {e}")
    finally:
        conn.close()

    print(f"Successfully inserted {inserted} samples into `synthetic_samples`.")
    return inserted


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest JSONL dataset into DB")
    parser.add_argument("--file", type=str, required=True, help="Path to JSONL file (e.g., data/val.jsonl)")
    parser.add_argument("--limit", type=int, default=500, help="Max tasks to ingest")
    args = parser.parse_args()
    
    ingest_file(args.file, limit=args.limit)
