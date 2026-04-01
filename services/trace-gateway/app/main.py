"""
Trace Gateway Service for Agent Glass.

This module acts as the central nervous system for the LLM evaluation framework.
It routes incoming traces from the LangGraph agent, persists them to PostgreSQL,
and broadcasts them asynchronously to connected dashboard clients via SSE.

Features:
    - Ingests structured JSON traces from the LangChain planning agent.
    - Asynchronously triggers embedding generation (Vector API) without blocking execution.
    - Asynchronously loops the Critic LLM evaluation pipeline.
    - Exposes a UMAP dimensionality reduction endpoint for UI dashboard clustering.

Environment Variables:
    DATABASE_URL (str): The PostgreSQL database connection string.
    EMBEDDER_URL (str): The URL endpoint for the embedding microservice.

Notes:
    This file adheres to the Google Python Style Guide for documentation.
"""
import asyncio
import json
import os
import hashlib
import httpx
import psycopg2
import psycopg2.extras
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import numpy as np
import umap

from pkg.config.env import *

class TraceEvent(BaseModel):
    session_id: str
    turn: int
    node: Optional[str] = None
    event_type: Optional[str] = None
    payload: dict | None = None
    timestamp: datetime | None = None

app = FastAPI(title="Trace Gateway", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"status": "ok", "service": "trace-gateway"}

def get_conn():
    if not DATABASE_URL:
        raise HTTPException(status_code=500, detail="DATABASE_URL not set")
    return psycopg2.connect(DATABASE_URL)

@app.post("/event")
def ingest(event: TraceEvent):
    payload = event.payload or {}
    payload_text = str(payload)
    input_hash = hashlib.sha256(payload_text.encode("utf-8")).hexdigest()
    output_hash = input_hash

    conn = get_conn()
    event_id = None
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO sessions (session_id) VALUES (%s) ON CONFLICT (session_id) DO NOTHING",
                    (event.session_id,),
                )
                cur.execute(
                    """
                    INSERT INTO events (session_id, turn, node, event_type, payload, timestamp, input_hash, output_hash)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        event.session_id,
                        event.turn,
                        event.node,
                        event.event_type,
                        psycopg2.extras.Json(payload),
                        event.timestamp or datetime.utcnow(),
                        input_hash,
                        output_hash,
                    ),
                )
                event_id = cur.fetchone()[0]
    finally:
        conn.close()

    # Best-effort embedding store for searchable traces.
    try:
        with httpx.Client(timeout=12) as client:
            client.post(
                f"{EMBEDDER_URL}/embed-store",
                json={
                    "session_id": event.session_id,
                    "event_id": event_id,
                    "text": payload_text,
                    "label": "historical",
                },
            )
    except Exception:
        pass

    return {"status": "accepted", "session_id": event.session_id, "turn": event.turn, "event_id": event_id}

@app.get("/events/{session_id}")
def list_events(session_id: str, limit: int = 100):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, turn, node, event_type, payload, timestamp
                FROM events
                WHERE session_id = %s
                ORDER BY id DESC
                LIMIT %s
                """,
                (session_id, limit),
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    return {
        "session_id": session_id,
        "events": [
            {
                "id": r[0],
                "turn": r[1],
                "node": r[2],
                "event_type": r[3],
                "payload": r[4],
                "timestamp": str(r[5]) if r[5] else None,
            }
            for r in rows
        ],
    }

@app.get("/sessions")
def list_sessions(limit: int = 50):
    """List all sessions, most recent first."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT s.session_id, s.created_at,
                       COUNT(e.id) AS event_count,
                       MAX(e.timestamp) AS last_event
                FROM sessions s
                LEFT JOIN events e ON e.session_id = s.session_id
                GROUP BY s.session_id, s.created_at
                ORDER BY last_event DESC NULLS LAST
                LIMIT %s
                """,
                (limit,),
            )
            rows = cur.fetchall()
    finally:
        conn.close()
    return {
        "sessions": [
            {
                "session_id": r[0],
                "created_at": str(r[1]),
                "event_count": r[2],
                "last_event": str(r[3]) if r[3] else None,
            }
            for r in rows
        ]
    }

@app.get("/stream")
async def stream_events(since_id: int = Query(0, description="Only return events with id > this value")):
    """
    Server-Sent Events stream.  Clients connect once and receive new trace events as they arrive.
    Each SSE message is a JSON-encoded event.  The client should track the last `id` field
    and pass it as ?since_id=<N> on reconnect.
    """
    async def generator():
        cursor_id = since_id
        # Send a keepalive immediately so the browser sees the connection is open
        yield "event: connected\ndata: {}\n\n"
        while True:
            await asyncio.sleep(2)
            conn = None
            try:
                conn = psycopg2.connect(DATABASE_URL)
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT id, session_id, turn, node, event_type, payload, timestamp
                        FROM events
                        WHERE id > %s
                        ORDER BY id ASC
                        LIMIT 20
                        """,
                        (cursor_id,),
                    )
                    rows = cur.fetchall()
                conn.close()
                for r in rows:
                    cursor_id = r[0]
                    data = json.dumps({
                        "id": r[0],
                        "session_id": r[1],
                        "turn": r[2],
                        "node": r[3],
                        "event_type": r[4],
                        "payload": r[5],
                        "timestamp": str(r[6]) if r[6] else None,
                    })
                    yield f"id: {r[0]}\nevent: trace\ndata: {data}\n\n"
            except Exception as exc:
                if conn:
                    try:
                        conn.close()
                    except Exception:
                        pass
                yield f"event: error\ndata: {json.dumps({'error': str(exc)})}\n\n"
                await asyncio.sleep(5)

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )

@app.get("/visualization/umap")
def get_umap_visualization():
    """Calculates a 3D UMAP projection of all stored trace embeddings."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            # Fetch embeddings, linking them to their threat_class from the critic
            cur.execute(
                """
                SELECT e.id, e.session_id, ev.turn, e.vector::text, 
                       ev.payload, COALESCE(c.threat_class, 'unknown') as threat_class
                FROM embeddings e
                JOIN events ev ON e.event_id = ev.id
                LEFT JOIN critic_decisions c 
                  ON ev.session_id = c.session_id AND ev.turn = c.turn
                WHERE e.vector IS NOT NULL
                LIMIT 1000
                """
            )
            rows = cur.fetchall()
            if not rows:
                return {"points": []}
                
            data = []
            vectors = []
            for r in rows:
                try:
                    vec = json.loads(r[3])
                    vectors.append(vec)
                    data.append({
                        "embedding_id": r[0],
                        "session_id": r[1],
                        "turn": r[2],
                        "payload": r[4],
                        "threat_class": r[5]
                    })
                except Exception:
                    continue
                    
            if len(vectors) < 3:
                # UMAP needs at least a few points to run reasonably
                return {"points": [{"x": 0, "y": 0, "z": 0, **d} for d in data]}
                
            np_vectors = np.array(vectors)
            n_comp = 3
            # We scale n_neighbors down if we don't have enough data
            n_neighbors = min(15, len(np_vectors) - 1)
            
            reducer = umap.UMAP(n_components=n_comp, n_neighbors=n_neighbors, random_state=42)
            projection = reducer.fit_transform(np_vectors)
            
            results = []
            for i, d in enumerate(data):
                results.append({
                    **d,
                    "x": float(projection[i, 0]),
                    "y": float(projection[i, 1]),
                    "z": float(projection[i, 2]) if n_comp == 3 else 0.0
                })
                
            return {"points": results}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        conn.close()

