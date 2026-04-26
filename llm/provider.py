# ==========================================
# LLM Provider (Ollama)
# ==========================================

from __future__ import annotations

import os
from functools import lru_cache
from typing import Any, Dict, List, Optional, Tuple

import requests
from dotenv import load_dotenv
from langchain_ollama import ChatOllama

load_dotenv()


# ------------------------------------------
# CONSTANTS
# ------------------------------------------
DEFAULT_REQUEST_TIMEOUT = 5


# ------------------------------------------
# CONFIG HELPERS
# ------------------------------------------
def _get_base_url() -> str:
    base_url = os.getenv("OLLAMA_BASE_URL", "").strip()
    if not base_url:
        raise ValueError("Missing OLLAMA_BASE_URL in .env")
    return base_url.rstrip("/")


def _safe_float_env(name: str, default: float) -> float:
    value = os.getenv(name, "").strip()
    if not value:
        return default

    try:
        return float(value)
    except ValueError:
        return default


def _safe_int_env(name: str, default: int) -> int:
    value = os.getenv(name, "").strip()
    if not value:
        return default

    try:
        return int(value)
    except ValueError:
        return default


def _resolve_model_name(task_type: str) -> str:
    """
    Resolve model by task type.

    Supported task types:
    - sql
    - router
    - explanation
    - general

    Env support:
    - OLLAMA_MODEL_SQL
    - OLLAMA_MODEL_ROUTER
    - OLLAMA_MODEL_EXPLANATION
    - OLLAMA_MODEL_GENERAL
    - OLLAMA_MODEL_Exp (legacy fallback, optional)
    """
    task = (task_type or "general").strip().lower()

    if task == "sql":
        model_name = os.getenv("OLLAMA_MODEL_SQL", "").strip()

    elif task == "router":
        model_name = (
            os.getenv("OLLAMA_MODEL_ROUTER", "").strip()
            or os.getenv("OLLAMA_MODEL_GENERAL", "").strip()
            or os.getenv("OLLAMA_MODEL_EXPLANATION", "").strip()
            or os.getenv("OLLAMA_MODEL_SQL", "").strip()
        )

    elif task == "explanation":
        model_name = (
            os.getenv("OLLAMA_MODEL_EXPLANATION", "").strip()
            or os.getenv("OLLAMA_MODEL_GENERAL", "").strip()
            or os.getenv("OLLAMA_MODEL_Exp", "").strip()
            or os.getenv("OLLAMA_MODEL_SQL", "").strip()
        )

    else:
        model_name = (
            os.getenv("OLLAMA_MODEL_GENERAL", "").strip()
            or os.getenv("OLLAMA_MODEL_EXPLANATION", "").strip()
            or os.getenv("OLLAMA_MODEL_Exp", "").strip()
            or os.getenv("OLLAMA_MODEL_SQL", "").strip()
        )

    if not model_name:
        raise ValueError(
            f"Missing Ollama model config for task_type='{task}'. "
            "Expected relevant OLLAMA_MODEL_* values in .env."
        )

    return model_name


def _task_settings(task_type: str) -> Dict[str, Any]:
    """
    Per-task LLM settings.

    Defaults are intentionally conservative to reduce GPU memory pressure.
    Each task can also be overridden from .env if needed.

    Supported overrides:
    - OLLAMA_TEMPERATURE_SQL
    - OLLAMA_TEMPERATURE_ROUTER
    - OLLAMA_TEMPERATURE_EXPLANATION
    - OLLAMA_TEMPERATURE_GENERAL
    - OLLAMA_NUM_CTX_SQL
    - OLLAMA_NUM_CTX_ROUTER
    - OLLAMA_NUM_CTX_EXPLANATION
    - OLLAMA_NUM_CTX_GENERAL
    """
    task = (task_type or "general").strip().lower()

    if task == "sql":
        return {
            "temperature": _safe_float_env("OLLAMA_TEMPERATURE_SQL", 0.0),
            "num_ctx": _safe_int_env("OLLAMA_NUM_CTX_SQL", 4096),
        }

    if task == "router":
        return {
            "temperature": _safe_float_env("OLLAMA_TEMPERATURE_ROUTER", 0.0),
            "num_ctx": _safe_int_env("OLLAMA_NUM_CTX_ROUTER", 1024),
        }

    if task == "explanation":
        return {
            "temperature": _safe_float_env("OLLAMA_TEMPERATURE_EXPLANATION", 0.2),
            "num_ctx": _safe_int_env("OLLAMA_NUM_CTX_EXPLANATION", 1024),
        }

    return {
        "temperature": _safe_float_env("OLLAMA_TEMPERATURE_GENERAL", 0.2),
        "num_ctx": _safe_int_env("OLLAMA_NUM_CTX_GENERAL", 2048),
    }


# ------------------------------------------
# SERVER CHECK
# ------------------------------------------
def check_ollama_server(base_url: str) -> Tuple[bool, Optional[str]]:
    try:
        response = requests.get(f"{base_url}/api/tags", timeout=DEFAULT_REQUEST_TIMEOUT)
        if response.status_code == 200:
            return True, None
        return False, f"Unexpected status code: {response.status_code}"
    except Exception as exc:
        return False, str(exc)


# ------------------------------------------
# MODEL CHECK
# ------------------------------------------
@lru_cache(maxsize=8)
def list_available_models(base_url: str) -> Tuple[str, ...]:
    """
    Return model names exposed by Ollama.
    Cached to reduce repeated /api/tags calls.
    """
    response = requests.get(f"{base_url}/api/tags", timeout=DEFAULT_REQUEST_TIMEOUT)
    response.raise_for_status()

    payload = response.json()
    models = payload.get("models", [])

    names: List[str] = []
    for item in models:
        name = item.get("name")
        if isinstance(name, str) and name.strip():
            names.append(name.strip())

    return tuple(names)


def check_model_available(base_url: str, model: str) -> Tuple[bool, List[str], Optional[str]]:
    """
    Check exact or base-name match.

    Example:
    requested: llama3.1:8b
    available: llama3.1:8b, llama3.1:latest

    Returns:
        (is_available, available_models, resolved_model_name)
    """
    try:
        model_names = list(list_available_models(base_url))
    except Exception:
        return False, [], None

    requested = (model or "").strip().lower()
    requested_base = requested.split(":", 1)[0]

    for name in model_names:
        if name.lower() == requested:
            return True, model_names, name

    for name in model_names:
        if name.lower().split(":", 1)[0] == requested_base:
            return True, model_names, name

    return False, model_names, None


# ------------------------------------------
# MAIN LLM FACTORY
# ------------------------------------------
@lru_cache(maxsize=12)
def get_llm(task_type: str = "general") -> ChatOllama:
    """
    Return an Ollama-backed ChatOllama instance based on task type.

    task_type:
    - "sql"         -> SQL generation / correction
    - "router"      -> intent classification
    - "explanation" -> explanation reasoning
    - "general"     -> default reasoning

    This function is cached so repeated calls reuse the same client config.
    """
    task = (task_type or "general").strip().lower()
    base_url = _get_base_url()
    requested_model_name = _resolve_model_name(task)
    settings = _task_settings(task)

    print(f"[LLM] Task: {task} -> Requested Model: {requested_model_name}")
    print(f"[LLM] Connecting to: {base_url}")
    print(
        f"[LLM] Settings -> temperature: {settings['temperature']}, "
        f"num_ctx: {settings['num_ctx']}"
    )

    # Validate server
    server_ok, server_error = check_ollama_server(base_url)
    if not server_ok:
        raise ConnectionError(f"Ollama server not reachable: {server_error}")

    # Validate model
    model_ok, available_models, resolved_model_name = check_model_available(base_url, requested_model_name)
    if not model_ok or not resolved_model_name:
        raise ValueError(
            f"Requested model '{requested_model_name}' not found in Ollama. "
            f"Available models: {available_models}"
        )

    print(f"[LLM] Using Model: {resolved_model_name}")

    return ChatOllama(
        model=resolved_model_name,
        base_url=base_url,
        temperature=settings["temperature"],
        num_ctx=settings["num_ctx"],
    )
