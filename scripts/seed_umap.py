#!/usr/bin/env python3
import os
import json
import uuid
import requests
import psycopg2
import psycopg2.extras
from datetime import datetime

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/agent_glass")
EMBEDDER_URL = "http://localhost:8005"

def seed_umap(limit=100):
    conn = psycopg2.connect(DATABASE_URL)
    
    with open("data/val.jsonl", "r", encoding="utf-8") as f:
        lines = f.readlines()[:limit]

    print(f"Seeding {len(lines)} samples for UMAP visualization...")
    
    for i, line in enumerate(lines):
        row = json.loads(line)
        category = row.get("category", "good")
        prompt = row.get("prompt", "")
        
        # Threat class mapping
        threat_class = "malicious" if category == "malicious" else "none"
        session_id = f"seed-session-{uuid.uuid4().hex[:8]}"
        turn = 1
        
        # Get embedding vector directly from embedder service
        try:
            resp = requests.post(f"{EMBEDDER_URL}/embed", json={"texts": [prompt], "provider": "nvidia"})
            resp.raise_for_status()
            vector = resp.json()["vectors"][0]
        except Exception as e:
            print(f"Failed to embed '{prompt[:30]}...': {e}")
            continue

        try:
            with conn:
                with conn.cursor() as cur:
                    # 1. Insert session
                    cur.execute("INSERT INTO sessions (session_id) VALUES (%s) ON CONFLICT DO NOTHING", (session_id,))
                    
                    # 2. Insert event
                    payload = {"role": "user", "content": prompt}
                    cur.execute(
                        """
                        INSERT INTO events (session_id, turn, node, event_type, payload, timestamp, input_hash, output_hash)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id
                        """,
                        (session_id, turn, "human", "message", psycopg2.extras.Json(payload), datetime.now(), "hash", "hash")
                    )
                    event_id = cur.fetchone()[0]
                    
                    # 3. Insert critic decision
                    cur.execute(
                        """
                        INSERT INTO critic_decisions (session_id, turn, decision, flag, threat_class, rationale)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        """,
                        (session_id, turn, "approve", "green" if threat_class == "none" else "red", threat_class, "Seeded for UMAP.")
                    )
                    
                    # 4. Insert embedding
                    v_literal = "[" + ",".join(f"{v:.8f}" for v in vector) + "]"
                    cur.execute(
                        """
                        INSERT INTO embeddings (session_id, event_id, label, provider, model, checksum, vector)
                        VALUES (%s, %s, %s, %s, %s, %s, (%s)::vector)
                        """,
                        (session_id, event_id, "historical", "nvidia", "nvidia/nv-embedqa-e5-v5", "chk", v_literal)
                    )
            print(f"[{i+1}/{len(lines)}] Successfully seeded '{category}' trace.")
        except Exception as e:
            print(f"DB Error: {e}")
            
    conn.close()
    print("Done seeding UMAP data.")

if __name__ == "__main__":
    seed_umap(150)
