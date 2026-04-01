"""
Router Service for Agent Glass.

This module provides an API gateway interface for processing incoming task requests.
It determines the appropriate LLM agent architecture to invoke based on task properties
such as task type, sensitivity, or required context length.

Features:
    - Inspects JSON payloads to dynamically route task execution.
    - Provides a robust boundary for throttling, tracking, or validating generic workloads.

Notes:
    This file adheres to the Google Python Style Guide for documentation.
"""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import os

class RouteRequest(BaseModel):
    task_type: str = Field(..., description="e.g. screening, planning, heavy_reasoning")
    context_length: int = 0
    sensitivity: str = Field("low", description="low|medium|high")
    deadline_ms: int | None = None

class RouteDecision(BaseModel):
    provider: str
    model: str
    rationale: str

app = FastAPI(title="LLM Router", version="0.2.0")

from pkg.config.env import *


@app.get("/health")
def health():
    return {"status": "ok", "service": "router"}

@app.get("/providers")
def providers():
    return {
        "nvidia": {"configured": bool(NVIDIA_API_KEY), "fast_model": NVIDIA_FAST_MODEL, "heavy_model": NVIDIA_HEAVY_MODEL},
    }

@app.post("/route", response_model=RouteDecision)
def route(req: RouteRequest):
    """
    Policy:
    - Use only NVIDIA provider.
    - Prefer fast model for short/low-sensitivity tasks.
    - Use heavy model for long context or high-sensitivity tasks.
    """
    rationale_parts = []

    if not NVIDIA_API_KEY:
        raise HTTPException(status_code=500, detail="NVIDIA_API_KEY not configured")

    long_ctx = req.context_length > 32000
    high_sens = req.sensitivity == "high"

    if high_sens:
        rationale_parts.append("sensitivity high → use sturdier tier")
    if long_ctx:
        rationale_parts.append("long context → heavy model")

    model = NVIDIA_HEAVY_MODEL if (long_ctx or high_sens) else NVIDIA_FAST_MODEL

    rationale = "; ".join(rationale_parts) or "default nvidia fast tier"
    return RouteDecision(provider="nvidia", model=model, rationale=rationale)
