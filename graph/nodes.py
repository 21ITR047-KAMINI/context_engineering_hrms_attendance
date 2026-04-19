# ==========================================
# Graph Nodes (LangGraph Execution Units)
# ==========================================

from __future__ import annotations

from typing import Any, Dict, List

from graph.state import AgentState

from agents.router_agent import router_agent
from agents.attendance_explanation_agent import reason_over_result

from rag.schema_selector import select_relevant_schema
from rag.schema_loader import load_schema
from rag.business_rules import get_rules
from rag.context_builder import build_context

from llm.prompt_builder import (
    build_sql_prompt,
    build_sql_correction_prompt,
)
from sql.sql_generator import generate_sql
from sql.sql_validator import validate_sql
from sql.result_processor import process_result

from sql.db_schema import get_db_schema
from tools.sql_tools import execute_sql


# ------------------------------------------
# INTERNAL HELPERS
# ------------------------------------------
VALID_INTENTS = {
    "attendance",
    "leave",
    "attendance_explanation",
    "policy",
    "irrelevant",
}


def _normalize_router_output(router_output: Any) -> str:
    """
    Normalize router output to one of:
    attendance, leave, attendance_explanation, policy, irrelevant
    """
    def _map_intent(raw: str) -> str:
        intent = (raw or "").strip().lower()

        alias_map = {
            "explanation": "attendance_explanation",
            "reasoning": "attendance_explanation",
            "why": "attendance_explanation",
            "shift": "attendance",
        }
        intent = alias_map.get(intent, intent)
        return intent if intent in VALID_INTENTS else "irrelevant"

    if isinstance(router_output, str):
        return _map_intent(router_output)

    if isinstance(router_output, dict):
        raw_intent = (
            router_output.get("intent")
            or router_output.get("route")
            or router_output.get("label")
            or "irrelevant"
        )
        return _map_intent(str(raw_intent))

    return "irrelevant"


def _infer_mode(intent: str) -> str:
    """
    Decide response mode.
    """
    if intent in {"attendance_explanation", "policy"}:
        return "reasoning"
    return "lookup"


def _normalize_db_result(result: Any) -> Dict[str, Any]:
    """
    Normalize DB result to a predictable structure.
    """
    normalized = {
        "rows": [],
        "columns": [],
        "error": None,
        "row_count": 0,
    }

    if result is None:
        normalized["error"] = "No result returned from database execution."
        return normalized

    if isinstance(result, dict):
        rows = result.get("rows", [])
        columns = result.get("columns", [])
        error = result.get("error")

        if rows is None:
            rows = []
        if columns is None:
            columns = []

        normalized["rows"] = rows
        normalized["columns"] = columns
        normalized["error"] = error
        normalized["row_count"] = len(rows) if isinstance(rows, list) else 0
        return normalized

    normalized["error"] = f"Unexpected DB result format: {type(result).__name__}"
    return normalized


def _safe_get_available_schema() -> Dict[str, Any]:
    """
    Load full DB schema catalog.
    Used as an allowlist so selector only returns real DB tables.
    """
    try:
        schema = get_db_schema()
        return schema if isinstance(schema, dict) else {}
    except Exception:
        return {}


def _clear_errors_for_retry() -> Dict[str, Any]:
    """
    Clear retry-related errors before regenerating SQL.
    """
    return {
        "validation_error": "",
        "db_error": "",
    }


def _extract_llm_context(structured_context: Dict[str, Any]) -> Dict[str, Any]:
    """
    The new RAG context_builder returns a rich structured dictionary.
    Prompt builders usually need the nested llm_context block.
    """
    if not isinstance(structured_context, dict):
        return {}

    llm_context = structured_context.get("llm_context", {})
    if isinstance(llm_context, dict) and llm_context:
        return llm_context

    return structured_context


# ------------------------------------------
# ROUTER NODE
# ------------------------------------------
def route_query_node(state: AgentState) -> Dict[str, Any]:
    """
    Classify the query intent and infer response mode.
    """
    query = state.get("query", "").strip()

    router_output = router_agent(query)
    intent = _normalize_router_output(router_output)
    mode = _infer_mode(intent)

    return {
        "intent": intent,
        "mode": mode,
        "retry_count": state.get("retry_count", 0),
        "max_retries": state.get("max_retries", 2),
    }


# ------------------------------------------
# SCHEMA SELECTION NODE
# ------------------------------------------
def schema_selection_node(state: AgentState) -> Dict[str, Any]:
    """
    Select relevant tables dynamically using the new RAG selector,
    then load full selected schema metadata from schema_docs.json.
    """
    query = state.get("query", "")
    intent = state.get("intent", "irrelevant")

    # DB schema is used as allowlist only.
    # Selector still uses all metadata present in schema_docs.json.
    available_schema = _safe_get_available_schema()

    selected_tables = select_relevant_schema(
        query=query,
        intent=intent,
        available_schema=available_schema,
        use_llm=True,
    )

    schema_context = load_schema(
        table_names=selected_tables,
        include_meta=False,
        strict=True,
    )

    return {
        "selected_tables": selected_tables,
        "schema_context": schema_context,
    }


# ------------------------------------------
# CONTEXT BUILDER NODE
# ------------------------------------------
def context_builder_node(state: AgentState) -> Dict[str, Any]:
    """
    Build structured RAG context from:
    - selected tables
    - selected schema metadata
    - business rules
    - join hints
    """
    query = state.get("query", "")
    intent = state.get("intent", "irrelevant")
    selected_tables = state.get("selected_tables", [])
    schema_context = state.get("schema_context", {})

    business_context = get_rules(
        intent=intent,
        tables=selected_tables,
        include_policy_json=True,
    )

    structured_context = build_context(
        query=query,
        intent=intent,
        schema=schema_context,
        rules=business_context,
    )

    llm_context = _extract_llm_context(structured_context)
    join_hints = structured_context.get("join_hints", []) if isinstance(structured_context, dict) else []

    return {
        "business_context": business_context,
        "join_hints": join_hints,
        "llm_context": llm_context,
        "full_context": structured_context,
    }


# ------------------------------------------
# SQL GENERATION NODE
# ------------------------------------------
def sql_generation_node(state: AgentState) -> Dict[str, Any]:
    """
    Generate SQL from the LLM-focused RAG context.
    """
    context = state.get("llm_context", {})

    prompt = build_sql_prompt(context)
    sql = generate_sql(prompt)

    return {
        "previous_sql": state.get("sql", ""),
        "sql": sql,
        "validation_error": "",
        "db_error": "",
    }


# ------------------------------------------
# SQL VALIDATION NODE
# ------------------------------------------
def sql_validation_node(state: AgentState) -> Dict[str, Any]:
    """
    Validate generated SQL before execution.
    """
    sql = state.get("sql", "")

    is_valid, message = validate_sql(sql)

    if is_valid:
        return {
            "validation_error": "",
        }

    return {
        "validation_error": message or "SQL validation failed.",
        "retry_count": state.get("retry_count", 0) + 1,
    }


# ------------------------------------------
# SQL EXECUTION NODE
# ------------------------------------------
def sql_execution_node(state: AgentState) -> Dict[str, Any]:
    """
    Execute validated SQL and normalize result.
    """
    sql = state.get("sql", "")

    raw_result = execute_sql(sql)
    db_result = _normalize_db_result(raw_result)

    if db_result.get("error"):
        return {
            "db_error": str(db_result["error"]),
            "db_result": db_result,
            "retry_count": state.get("retry_count", 0) + 1,
        }

    return {
        "db_error": "",
        "db_result": db_result,
    }


# ------------------------------------------
# SQL CORRECTION NODE
# ------------------------------------------
def sql_correction_node(state: AgentState) -> Dict[str, Any]:
    """
    Regenerate SQL using validation/db error feedback
    while keeping the same RAG context.
    """
    context = state.get("llm_context", {})
    previous_sql = state.get("sql", "")
    validation_error = state.get("validation_error", "")
    db_error = state.get("db_error", "")

    correction_prompt = build_sql_correction_prompt(
        context=context,
        previous_sql=previous_sql,
        validation_error=validation_error,
        db_error=db_error,
    )

    corrected_sql = generate_sql(correction_prompt)

    cleared_errors = _clear_errors_for_retry()
    cleared_errors.update(
        {
            "previous_sql": previous_sql,
            "sql": corrected_sql,
        }
    )
    return cleared_errors


# ------------------------------------------
# RESULT REASONING NODE
# ------------------------------------------
def result_reasoning_node(state: AgentState) -> Dict[str, Any]:
    """
    Build final user-facing response.

    Modes:
    - lookup: simple formatting of DB results
    - reasoning: explanation based on evidence + business rules + RAG context
    """
    query = state.get("query", "")
    intent = state.get("intent", "irrelevant")
    mode = state.get("mode", "lookup")
    db_result = state.get("db_result", {})

    if intent == "irrelevant":
        return {
            "response": "Question is irrelevant, can be processed in future."
        }

    if db_result.get("error"):
        if state.get("retry_count", 0) >= state.get("max_retries", 2):
            return {
                "response": "Data not found"
            }

    rows = db_result.get("rows", [])
    if not rows:
        return {
            "response": "Data not found"
        }

    if mode == "reasoning":
        response = reason_over_result(
            query=query,
            result=db_result,
            context=state.get("full_context", state.get("llm_context", {})),
        )
        return {
            "response": response
        }

    response = process_result(db_result, query)
    return {
        "response": response
    }


# ------------------------------------------
# CONDITIONAL EDGE HELPERS
# ------------------------------------------
def should_continue_after_routing(state: AgentState) -> str:
    """
    Decide whether to continue pipeline or stop as irrelevant.
    """
    if state.get("intent") == "irrelevant":
        return "irrelevant"
    return "continue"


def should_retry_after_validation(state: AgentState) -> str:
    """
    After SQL validation:
    - correction -> validation error and retries available
    - finish     -> validation error and retries exhausted
    - execute    -> validation passed
    """
    validation_error = state.get("validation_error", "")
    retry_count = state.get("retry_count", 0)
    max_retries = state.get("max_retries", 2)

    if validation_error:
        if retry_count <= max_retries:
            return "correction"
        return "finish"

    return "execute"


def should_retry_after_execution(state: AgentState) -> str:
    """
    After SQL execution:
    - correction -> DB error and retries available
    - finish     -> DB error and retries exhausted
    - finish     -> success
    """
    db_error = state.get("db_error", "")
    retry_count = state.get("retry_count", 0)
    max_retries = state.get("max_retries", 2)

    if db_error:
        if retry_count <= max_retries:
            return "correction"
        return "finish"

    return "finish"
