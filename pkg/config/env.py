"""
Central Configuration Module for Agent Glass.

Parses shared environment variables to ensure zero duplication
across the 7 microservices.
"""
import os

DATABASE_URL = os.getenv("DATABASE_URL")

ROUTER_URL = os.getenv("ROUTER_URL", "http://router:8000")
TRACE_GATEWAY_URL = os.getenv("TRACE_GATEWAY_URL", "http://trace-gateway:8000")
CRITIC_URL = os.getenv("CRITIC_URL", "http://critic:8000")
EMBEDDER_URL = os.getenv("EMBEDDER_URL", "http://embedder:8000")

NVIDIA_BASE_URL = os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY")

DEFAULT_NVIDIA_FAST_MODEL = os.getenv("NVIDIA_FAST_MODEL", "nvidia/nemotron-mini-4b-instruct")
DEFAULT_NVIDIA_HEAVY_MODEL = os.getenv("NVIDIA_HEAVY_MODEL", "meta/llama-3.1-70b-instruct")
DEFAULT_NVIDIA_EMBED_MODEL = os.getenv("NVIDIA_EMBED_MODEL", "nvidia/nv-embed-v1")

LOOP_LOOKBACK = 5
LOOP_THRESHOLD = 4
