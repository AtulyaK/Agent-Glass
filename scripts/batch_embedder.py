#!/usr/bin/env python3
import os
import json
import uuid
import time
import requests
import psycopg2
import psycopg2.extras
from datetime import datetime

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/agent_glass")
EMBEDDER_URL = "http://localhost:8005"

def batch_embed(filepath="data/val.jsonl", limit=1000):
    conn = psycopg2.connect(DATABASE_URL)
    
    # Read samples
    samples = []
    with open(filepath, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if i >= limit:
                break
            samples.append(json.loads(line))

    print(f"Batch embedding {len(samples)} samples with rate limit protection...")
    
    success_count = 0
    for i, row in enumerate(samples):
        category = row.get("category", "good")
        prompt = row.get("prompt", "")
        
        # Threat class mapping
        threat_class = "malicious" if category == "malicious" else "none"
        session_id = f"batch-session-{uuid.uuid4().hex[:8]}"
        turn = 1
        
        # Embed with exponential backoff for 429 Too Many Requests
        vector = None
        retries = 0
        max_retries = 5
        base_sleep = 5
        
        while retries < max_retries:
            try:
                resp = requests.post(f"{EMBEDDER_URL}/embed", json={"texts": [prompt], "provider": "nvidia"})
                
                if resp.status_code == 429:
                    sleep_time = base_sleep * (2 ** retries)
                    print(f"Rate limited (429). Sleeping for {sleep_time} seconds...")
                    time.sleep(sleep_time)
                    retries += 1
                    continue
                    
                resp.raise_for_status()
                vector = resp.json()["vectors"][0]
                break
                
            except Exception as e:
                print(f"Failed to embed item {i}: {e}")
                time.sleep(2)  # Short sleep on general errors
                retries += 1
                
        if not vector:
            print(f"Skipping item {i} after {max_retries} failed attempts.")
            continue

        try:
            with conn:
                with conn.cursor() as cur:
                    cur.execute("INSERT INTO sessions (session_id) VALUES (%s) ON CONFLICT DO NOTHING", (session_id,))
                    
                    payload = {"role": "user", "content": prompt}
                    cur.execute(
                        """
                        INSERT INTO events (session_id, turn, node, event_type, payload, timestamp, input_hash, output_hash)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id
                        """,
                        (session_id, turn, "human", "message", psycopg2.extras.Json(payload), datetime.now(), "hash", "hash")
                    )
                    event_id = cur.fetchone()[0]
                    
                    cur.execute(
                        """
                        INSERT INTO critic_decisions (session_id, turn, decision, flag, threat_class, rationale)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        """,
                        (session_id, turn, "approve", "green" if threat_class == "none" else "red", threat_class, "Batch seeded.")
                    )
                    
                    v_literal = "[" + ",".join(f"{v:.8f}" for v in vector) + "]"
                    # We are using nvidia/nv-embed-v1 which outputs 4096 dimensions
                    cur.execute(
                        """
                        INSERT INTO embeddings (session_id, event_id, label, provider, model, checksum, vector)
                        VALUES (%s, %s, %s, %s, %s, %s, (%s)::vector)
                        """,
                        (session_id, event_id, "historical", "nvidia", "nvidia/nv-embed-v1", "chk", v_literal)
                    )
            success_count += 1
            if success_count % 10 == 0:
                print(f"[{success_count}] Successfully embedded trace.")
                
        except Exception as e:
            print(f"DB Error on item {i}: {e}")
            
    conn.close()
    print(f"Done! Successfully batch embedded {success_count} samples.")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=150)
    args = parser.parse_args()
    batch_embed(limit=args.limit)
