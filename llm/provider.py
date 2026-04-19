# ==========================================
# LLM Provider (Ollama with Validation)
# ==========================================

from langchain_ollama import ChatOllama
import requests
import os
from dotenv import load_dotenv

load_dotenv()


# ------------------------------------------
# SERVER CHECK
# ------------------------------------------
def check_ollama_server(base_url: str):
    try:
        res = requests.get(f"{base_url}/api/tags", timeout=3)
        return res.status_code == 200, None
    except Exception as e:
        return False, str(e)


# ------------------------------------------
# MODEL CHECK
# ------------------------------------------
def check_model_available(base_url: str, model: str):
    try:
        res = requests.get(f"{base_url}/api/tags", timeout=3)
        models = res.json().get("models", [])
        model_names = [m["name"] for m in models]

        return model in model_names, model_names
    except Exception as e:
        return False, str(e)


# ------------------------------------------
# MAIN LLM FACTORY
# ------------------------------------------
def get_llm(task_type: str = "general"):
    """
    Returns appropriate LLM based on task type.
    
    task_type:
    - "sql" → SQL generation
    - "router" → intent classification
    - "explanation" → reasoning
    - "general" → default
    """

    base_url = os.getenv("OLLAMA_BASE_URL")

    # --------------------------------------
    #  MODEL SELECTION
    # --------------------------------------
    if task_type == "sql":
        model_name = os.getenv("OLLAMA_MODEL_SQL")

    else:
        model_name = os.getenv("OLLAMA_MODEL_Exp")

    print(f"[LLM] Task: {task_type} → Model: {model_name}")

    

    if not base_url or not model_name:
        raise ValueError("Missing OLLAMA config in .env")

    print(f"[LLM] Connecting to: {base_url}")
    print(f"[LLM] Model: {model_name}")

    # Validate server
    server_ok, server_error = check_ollama_server(base_url)
    if not server_ok:
        raise ConnectionError(f"Ollama not reachable: {server_error}")

    # Validate model
    model_ok, model_info = check_model_available(base_url, model_name)
    if not model_ok:
        raise ValueError(f"Model not found. Available: {model_info}")

    # Initialize model
    return ChatOllama(
        model=model_name,
        base_url=base_url,
        temperature=0.2,     # tuned for SQL
        num_ctx=4096         # supports RAG context
    )