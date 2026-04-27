# ==========================================
# LLM Provider (Ollama + Gemini)
# ==========================================

from __future__ import annotations

import os
from functools import lru_cache
from typing import Any, Dict, List, Optional, Tuple

import requests
from dotenv import load_dotenv
from langchain_ollama import ChatOllama
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()


# ------------------------------------------
# CONSTANTS
# ------------------------------------------
DEFAULT_REQUEST_TIMEOUT = 5
DEFAULT_PROVIDER = "ollama"


# ------------------------------------------
# CONFIG HELPERS
# ------------------------------------------
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


def _get_provider() -> str:
    provider = os.getenv("LLM_PROVIDER", DEFAULT_PROVIDER).strip().lower()
    if provider not in {"ollama", "gemini"}:
        raise ValueError(
            "Invalid LLM_PROVIDER. Supported values: 'ollama' or 'gemini'."
        )
    return provider


def _get_ollama_base_url() -> str:
    base_url = os.getenv("OLLAMA_BASE_URL", "").strip()
    if not base_url:
        raise ValueError("Missing OLLAMA_BASE_URL in .env")
    return base_url.rstrip("/")


def _resolve_ollama_model_name(task_type: str) -> str:
    """
    Resolve Ollama model by task type.
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


def _resolve_gemini_model_name(task_type: str) -> str:
    """
    Resolve Gemini model by task type.

    Supported env vars:
    - GEMINI_MODEL_SQL
    - GEMINI_MODEL_ROUTER
    - GEMINI_MODEL_EXPLANATION
    - GEMINI_MODEL_GENERAL
    - GEMINI_MODEL (global fallback, defaults to gemini-2.5-flash)
    """
    task = (task_type or "general").strip().lower()
    global_default = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()

    if task == "sql":
        model_name = os.getenv("GEMINI_MODEL_SQL", "").strip() or global_default
    elif task == "router":
        model_name = (
            os.getenv("GEMINI_MODEL_ROUTER", "").strip()
            or os.getenv("GEMINI_MODEL_GENERAL", "").strip()
            or os.getenv("GEMINI_MODEL_EXPLANATION", "").strip()
            or global_default
        )
    elif task == "explanation":
        model_name = (
            os.getenv("GEMINI_MODEL_EXPLANATION", "").strip()
            or os.getenv("GEMINI_MODEL_GENERAL", "").strip()
            or global_default
        )
    else:
        model_name = os.getenv("GEMINI_MODEL_GENERAL", "").strip() or global_default

    if not model_name:
        raise ValueError("Missing Gemini model configuration in .env")

    return model_name


def _task_settings(task_type: str) -> Dict[str, Any]:
    """
    Provider-agnostic per-task LLM settings.
    """
    task = (task_type or "general").strip().lower()

    if task == "sql":
        return {
            "temperature": _safe_float_env("LLM_TEMPERATURE_SQL", 0.0),
            "num_ctx": _safe_int_env("LLM_NUM_CTX_SQL", 4096),
        }

    if task == "router":
        return {
            "temperature": _safe_float_env("LLM_TEMPERATURE_ROUTER", 0.0),
            "num_ctx": _safe_int_env("LLM_NUM_CTX_ROUTER", 1024),
        }

    if task == "explanation":
        return {
            "temperature": _safe_float_env("LLM_TEMPERATURE_EXPLANATION", 0.2),
            "num_ctx": _safe_int_env("LLM_NUM_CTX_EXPLANATION", 1024),
        }

    return {
        "temperature": _safe_float_env("LLM_TEMPERATURE_GENERAL", 0.2),
        "num_ctx": _safe_int_env("LLM_NUM_CTX_GENERAL", 2048),
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


@lru_cache(maxsize=12)
def get_llm(task_type: str = "general") -> Any:
    """
    Return an LLM instance based on the selected provider.

    Set `LLM_PROVIDER=ollama` (default) or `LLM_PROVIDER=gemini`.
    """
    task = (task_type or "general").strip().lower()
    provider = _get_provider()
    settings = _task_settings(task)

    print(f"[LLM] Provider: {provider} | Task: {task}")
    print(
        f"[LLM] Settings -> temperature: {settings['temperature']}, "
        f"num_ctx: {settings['num_ctx']}"
    )

    if provider == "gemini":
        api_key = os.getenv("GEMINI_API_KEY", "").strip()
        if not api_key:
            raise ValueError("Missing GEMINI_API_KEY in .env")

        model_name = _resolve_gemini_model_name(task)
        print(f"[LLM] Gemini model: {model_name}")

        return ChatGoogleGenerativeAI(
            model=model_name,
            temperature=settings["temperature"],
            google_api_key=api_key,
        )

    base_url = _get_ollama_base_url()
    requested_model_name = _resolve_ollama_model_name(task)

    print(f"[LLM] Ollama requested model: {requested_model_name}")
    print(f"[LLM] Connecting to: {base_url}")

    server_ok, server_error = check_ollama_server(base_url)
    if not server_ok:
        raise ConnectionError(f"Ollama server not reachable: {server_error}")

    model_ok, available_models, resolved_model_name = check_model_available(base_url, requested_model_name)
    if not model_ok or not resolved_model_name:
        raise ValueError(
            f"Requested model '{requested_model_name}' not found in Ollama. "
            f"Available models: {available_models}"
        )

    print(f"[LLM] Using Ollama model: {resolved_model_name}")

    return ChatOllama(
        model=resolved_model_name,
        base_url=base_url,
        temperature=settings["temperature"],
        num_ctx=settings["num_ctx"],
    )
