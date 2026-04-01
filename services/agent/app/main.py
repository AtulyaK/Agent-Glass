"""
Agent Service for Agent Glass.

This module acts as the core LLM execution proxy. It leverages LangGraph to rigidly
enforce state progression, breaking down naive LLM objectives into intercepted nodes.

Graph Topology:
    plan_node → trace_plan_node → simulate_tool_node → trace_tool_node → END

Features:
    - Automatically traces complex planning execution loops.
    - Yields asynchronous observation hooks prior to deterministic actions.
    - Communicates heavily with the trace-gateway and router nodes.

Environment Variables:
    ROUTER_URL (str): Origin URL for API routing interactions.
    TRACE_GATEWAY_URL (str): The centralized Observability message bus.
    NVIDIA_HEAVY_MODEL (str): Mapping for the primary reasoning LLM parameters.

Notes:
    This file adheres to the Google Python Style Guide for documentation.
"""
import os
import random
import httpx
from typing import Any, TypedDict

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import OpenAI

from langgraph.graph import StateGraph, END

# ── Config ────────────────────────────────────────────────────────────────────
from pkg.config.env import *

# ── FastAPI models ────────────────────────────────────────────────────────────
class PlanRequest(BaseModel):
    session_id: str
    objective: str
    context_length: int | None = None
    sensitivity: str | None = "low"

class PlanResponse(BaseModel):
    plan: list
    message: str
    provider: str
    model: str
    session_id: str
    tool_simulation: dict | None = None

app = FastAPI(title="Agent", version="0.3.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── LangGraph State ───────────────────────────────────────────────────────────
class AgentState(TypedDict):
    session_id: str
    objective: str
    sensitivity: str
    model: str
    plan_steps: list          # list of {step, action}
    plan_trace_id: int | None # event id returned by trace-gateway
    tool_result: dict         # simulated tool call result
    tool_trace_id: int | None # event id for tool call

# ── Helpers ───────────────────────────────────────────────────────────────────
def _nvidia_client() -> OpenAI:
    if not NVIDIA_API_KEY:
        raise HTTPException(status_code=500, detail="NVIDIA_API_KEY not set")
    return OpenAI(api_key=NVIDIA_API_KEY, base_url=NVIDIA_BASE_URL)

def _emit_trace(session_id: str, turn: int, node: str, event_type: str, payload: dict) -> int | None:
    """Fire-and-forget trace event. Returns event_id or None on failure."""
    try:
        with httpx.Client(timeout=10) as client:
            resp = client.post(
                f"{TRACE_GATEWAY_URL}/event",
                json={
                    "session_id": session_id,
                    "turn": turn,
                    "node": node,
                    "event_type": event_type,
                    "payload": payload,
                },
            )
            resp.raise_for_status()
            return resp.json().get("event_id")
    except Exception:
        return None

def _call_router(objective: str, context_length: int | None, sensitivity: str | None) -> dict:
    payload = {
        "task_type": "planning",
        "context_length": context_length or len(objective),
        "sensitivity": sensitivity or "low",
    }
    with httpx.Client(timeout=10) as client:
        r = client.post(f"{ROUTER_URL}/route", json=payload)
        r.raise_for_status()
        return r.json()

# ── LangGraph Nodes ───────────────────────────────────────────────────────────
def plan_node(state: AgentState) -> AgentState:
    """Ask the LLM to break the objective into concrete steps."""
    client = _nvidia_client()
    system_prompt = (
        "You are an AI agent planner. Given an objective, return ONLY a numbered list "
        "of concrete action steps (3–5 steps). Each step should be a short imperative sentence. "
        "Do not include any preamble or explanation."
    )
    completion = client.chat.completions.create(
        model=state["model"],
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Objective: {state['objective']}"},
        ],
        max_tokens=300,
    )
    text = completion.choices[0].message.content or ""
    steps = []
    for i, line in enumerate(text.splitlines()):
        stripped = line.strip()
        if not stripped:
            continue
        # Strip leading numbering like "1." or "1)"
        action = stripped.lstrip("0123456789.)- ").strip()
        if action:
            steps.append({"step": len(steps) + 1, "action": action})
    if not steps:
        steps = [{"step": 1, "action": text.strip()[:200]}]
    return {**state, "plan_steps": steps}

def trace_plan_node(state: AgentState) -> AgentState:
    """Emit the generated plan as a trace event."""
    event_id = _emit_trace(
        session_id=state["session_id"],
        turn=1,
        node="plan_node",
        event_type="plan_created",
        payload={
            "objective": state["objective"],
            "steps": state["plan_steps"],
            "model": state["model"],
        },
    )
    return {**state, "plan_trace_id": event_id}

def simulate_tool_node(state: AgentState) -> AgentState:
    """
    Symbolically execute step 1 of the plan.
    Randomly introduces a 20% failure rate so we can exercise the critic's
    roadblock detection path even in early development.
    """
    first_step = state["plan_steps"][0]["action"] if state["plan_steps"] else "no-op"
    # Infer a plausible tool name from the action verb
    tool_name = "web_search"
    action_lower = first_step.lower()
    if any(w in action_lower for w in ["read", "open", "load", "fetch", "retrieve", "get"]):
        tool_name = "file_reader"
    elif any(w in action_lower for w in ["write", "save", "store", "create", "generate"]):
        tool_name = "file_writer"
    elif any(w in action_lower for w in ["api", "call", "send", "post", "request"]):
        tool_name = "api_caller"
    elif any(w in action_lower for w in ["analyze", "compute", "calculate", "process"]):
        tool_name = "code_executor"

    success = random.random() > 0.2  # 80% success
    result = {
        "tool": tool_name,
        "step": first_step,
        "status": "success" if success else "failure",
        "output": (
            f"[simulated] Tool '{tool_name}' executed step successfully."
            if success
            else f"[simulated] Tool '{tool_name}' failed: resource unavailable."
        ),
    }
    return {**state, "tool_result": result}

def trace_tool_node(state: AgentState) -> AgentState:
    """Emit the tool call result as a trace event."""
    event_id = _emit_trace(
        session_id=state["session_id"],
        turn=2,
        node="simulate_tool_node",
        event_type="tool_call",
        payload=state["tool_result"],
    )
    return {**state, "tool_trace_id": event_id}

# ── Build LangGraph ───────────────────────────────────────────────────────────
def _build_graph():
    wf = StateGraph(AgentState)
    wf.add_node("plan", plan_node)
    wf.add_node("trace_plan", trace_plan_node)
    wf.add_node("simulate_tool", simulate_tool_node)
    wf.add_node("trace_tool", trace_tool_node)

    wf.set_entry_point("plan")
    wf.add_edge("plan", "trace_plan")
    wf.add_edge("trace_plan", "simulate_tool")
    wf.add_edge("simulate_tool", "trace_tool")
    wf.add_edge("trace_tool", END)

    return wf.compile()

_graph = _build_graph()

# ── FastAPI Endpoints ─────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok", "service": "agent", "graph_nodes": list(_graph.get_graph().nodes.keys())}

@app.post("/plan", response_model=PlanResponse)
def plan(req: PlanRequest):
    # 1. Route to get model
    try:
        route = _call_router(req.objective, req.context_length, req.sensitivity)
    except Exception as err:
        raise HTTPException(status_code=502, detail=f"router unreachable: {err}")

    provider = route.get("provider", "nvidia")
    model = route.get("model") or DEFAULT_NVIDIA_HEAVY_MODEL

    if provider != "nvidia":
        raise HTTPException(status_code=400, detail=f"Unsupported provider: {provider}")

    # 2. Run LangGraph
    initial_state: AgentState = {
        "session_id": req.session_id,
        "objective": req.objective,
        "sensitivity": req.sensitivity or "low",
        "model": model,
        "plan_steps": [],
        "plan_trace_id": None,
        "tool_result": {},
        "tool_trace_id": None,
    }

    try:
        final_state = _graph.invoke(initial_state)
    except Exception as err:
        raise HTTPException(status_code=502, detail=f"agent graph failed: {err}")

    return PlanResponse(
        plan=final_state["plan_steps"],
        message=f"planned via nvidia ({model}) — tool sim: {final_state['tool_result'].get('status', 'n/a')}",
        provider=provider,
        model=model,
        session_id=req.session_id,
        tool_simulation=final_state["tool_result"],
    )
