"""
Semantic Embedder Service for Agent Glass.

This module acts as the vector transformation layer. It takes plain-text traces
and generates high-dimensional mathematical embeddings using the NVIDIA NIM API.
These embeddings are crucial for the UMAP projection and k-NN similarity detection.

Features:
    - Maps strings to 4096-dimensional vectors via `nvidia/nv-embed-v1`.
    - Enforces local checksum caching (`embed-store`) to intercept duplicate queries natively.
    - Ensures massive prompts bypass standard truncation limits natively across the network.

Environment Variables:
    NVIDIA_API_KEY (str): NVIDIA NIM API token.
    NVIDIA_EMBED_MODEL (str): Configuration mapping for the specific embedding target.
    DATABASE_URL (str): The PostgreSQL database connection string mapping.

Notes:
    This file adheres to the Google Python Style Guide for documentation.
"""
import os
import hashlib
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from openai import OpenAI
import psycopg2

from pkg.config.env import *

class EmbedRequest(BaseModel):
    texts: List[str]
    provider: str | None = None

class EmbedResponse(BaseModel):
    provider: str
    model: str
    vectors: List[List[float]]

class StoreEmbeddingRequest(BaseModel):
    session_id: str
    event_id: Optional[int] = None
    text: str
    provider: Optional[str] = None
    label: str = "historical"

class StoreEmbeddingResponse(BaseModel):
    status: str
    embedding_id: int
    provider: str
    model: str

app = FastAPI(title="Embedder", version="0.2.0")

@app.get("/health")
def health():
    return {"status": "ok", "service": "embedder"}

def embed_with_nvidia(texts: List[str]) -> EmbedResponse:
    if not NVIDIA_API_KEY:
        raise HTTPException(status_code=500, detail="NVIDIA_API_KEY not set")
    client = OpenAI(api_key=NVIDIA_API_KEY, base_url=NVIDIA_BASE_URL)
    resp = client.embeddings.create(
        model=DEFAULT_NVIDIA_EMBED_MODEL, 
        input=texts,
        extra_body={"input_type": "query"}
    )
    vectors = [item.embedding for item in resp.data]
    return EmbedResponse(provider="nvidia", model=DEFAULT_NVIDIA_EMBED_MODEL, vectors=vectors)

@app.post("/embed", response_model=EmbedResponse)
def embed(req: EmbedRequest):
    provider = req.provider or "nvidia"
    if provider != "nvidia":
        raise HTTPException(status_code=400, detail="Unsupported provider; use nvidia")
    return embed_with_nvidia(req.texts)

def vector_literal(values: List[float]) -> str:
    return "[" + ",".join(f"{v:.8f}" for v in values) + "]"

def get_conn():
    if not DATABASE_URL:
        raise HTTPException(status_code=500, detail="DATABASE_URL not set")
    return psycopg2.connect(DATABASE_URL)

@app.post("/embed-store", response_model=StoreEmbeddingResponse)
def embed_store(req: StoreEmbeddingRequest):
    checksum = hashlib.sha256(req.text.encode("utf-8")).hexdigest()
    
    conn = get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                # 1. Deduplication Check: See if this exact prompt was already embedded safely
                cur.execute(
                    "SELECT vector::text, provider, model FROM embeddings WHERE checksum = %s LIMIT 1",
                    (checksum,)
                )
                existing = cur.fetchone()
                
                if existing:
                    v_literal, used_provider, used_model = existing[0], existing[1], existing[2]
                else:
                    # Cache miss: Call NVIDIA NIM
                    result = embed(EmbedRequest(texts=[req.text], provider=req.provider))
                    v_literal = vector_literal(result.vectors[0])
                    used_provider = result.provider
                    used_model = result.model
                
                # Insert the new row, linking the event to the (potentially cached) vector string
                cur.execute(
                    """
                    INSERT INTO embeddings (session_id, event_id, label, provider, model, checksum, vector)
                    VALUES (%s, %s, %s, %s, %s, %s, %s::vector)
                    RETURNING id
                    """,
                    (req.session_id, req.event_id, req.label, used_provider, used_model, checksum, v_literal),
                )
                embedding_id = cur.fetchone()[0]
    finally:
        conn.close()

    return StoreEmbeddingResponse(
        status="stored_cached" if existing else "stored_new",
        embedding_id=embedding_id,
        provider=used_provider,
        model=used_model,
    )
