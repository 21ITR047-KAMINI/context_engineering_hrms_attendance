# ==========================================
# Graph Nodes (LangGraph Execution Units)
# ==========================================

from __future__ import annotations

from typing import Any, Dict

from graph.state import AgentState

from agents.router_agent import router_agent
from agents.attendance_explanation_agent import reason_over_result
from constants import FALLBACK_QUERY_ERROR_MESSAGE

from rag.schema_selector import select_schema_bundle
from rag.business_rules import get_rules
from rag.context_builder import build_context

from sql.sql_generator import generate_sql, correct_sql
from sql.sql_validator import validate_sql
from sql.result_processor import process_result

from sql.db_schema import get_db_schema
from tools.sql_tools import execute_sql, fetch_table_sample
from tools.result_tool import format_table_view


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
    if isinstance(router_output, str):
        intent = router_output.strip().lower()
        return intent if intent in VALID_INTENTS else "irrelevant"

    if isinstance(router_output, dict):
        raw_intent = (
            router_output.get("intent")
            or router_output.get("route")
            or router_output.get("label")
            or "irrelevant"
        )
        intent = str(raw_intent).strip().lower()
        return intent if intent in VALID_INTENTS else "irrelevant"

    return "irrelevant"


def _infer_mode(intent: str, query: str) -> str:
    query_lower = (query or "").strip().lower()

    if intent in {"attendance_explanation", "policy"}:
        return "reasoning"

    if any(x in query_lower for x in ["why", "reason", "explain"]):
        return "reasoning"

    return "lookup"


def _normalize_db_result(result: Any) -> Dict[str, Any]:
    normalized = {
        "rows": result.get("rows", []) if isinstance(result, dict) else [],
        "columns": result.get("columns", []) if isinstance(result, dict) else [],
        "error": result.get("error") if isinstance(result, dict) else None,
        "row_count": len(result.get("rows", [])) if isinstance(result, dict) else 0,
    }
    return normalized


def _safe_get_available_schema() -> Dict[str, Any]:
    try:
        schema = get_db_schema()
        print("[DB_SCHEMA] Loaded usable DB schema tables:", list(schema.keys()) if isinstance(schema, dict) else [])
        return schema if isinstance(schema, dict) else {}
    except Exception as e:
        print("[DB_SCHEMA ERROR]:", str(e))
        return {}


# ------------------------------------------
# ROUTER NODE
# ------------------------------------------
def route_query_node(state: AgentState) -> Dict[str, Any]:
    query = state.get("query", "").strip()

    print("\n=== NODE: route_query ===")
    print("[INPUT QUERY]:", query)

    router_output = router_agent(query)
    intent = _normalize_router_output(router_output)
    mode = _infer_mode(intent, query)

    print("[ROUTE NODE OUTPUT] intent:", intent)
    print("[ROUTE NODE OUTPUT] mode:", mode)
    print("[ROUTE NODE OUTPUT] retry_count:", state.get("retry_count", 0))
    print("[ROUTE NODE OUTPUT] max_retries:", state.get("max_retries", 2))

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
    query = state.get("query", "")
    intent = state.get("intent", "irrelevant")

    print("\n=== NODE: schema_selection ===")
    print("[SCHEMA_SELECTION INPUT] query:", query)
    print("[SCHEMA_SELECTION INPUT] intent:", intent)

    available_schema = _safe_get_available_schema()

    schema_bundle = select_schema_bundle(
        query=query,
        intent=intent,
        available_schema=available_schema,
        use_llm=True,
    )

    selected_tables = schema_bundle.get("selected_tables", [])
    selected_schema = schema_bundle.get("selected_schema", {})
    selected_columns = schema_bundle.get("selected_columns", {})

    print("[SCHEMA_SELECTION OUTPUT] selected_tables:", selected_tables)
    print("[SCHEMA_SELECTION OUTPUT] selected_columns:", selected_columns)
    print("[SCHEMA_SELECTION OUTPUT] selected_schema_tables:", list(selected_schema.keys()))

    return {
        "selected_tables": selected_tables,
        "schema_context": selected_schema,
    }


# ------------------------------------------
# CONTEXT BUILDER NODE
# ------------------------------------------
def context_builder_node(state: AgentState) -> Dict[str, Any]:
    query = state.get("query", "")
    intent = state.get("intent", "irrelevant")
    selected_tables = state.get("selected_tables", [])
    schema_context = state.get("schema_context", {})

    print("\n=== NODE: context_builder ===")
    print("[CONTEXT INPUT] selected_tables:", selected_tables)
    print("[CONTEXT INPUT] schema_context_tables:", list(schema_context.keys()) if isinstance(schema_context, dict) else [])

    business_context = get_rules(intent=intent, tables=selected_tables)

    structured_context = build_context(
        query=query,
        intent=intent,
        schema=schema_context,
        rules=business_context,
    )
    table_samples = {}

    for table in selected_tables:
        table_samples[table] = fetch_table_sample(table, limit=2)
    
    llm_context = structured_context.get("llm_context", structured_context)

    print("[CONTEXT OUTPUT] business_rule_count:", len(business_context))
    print("[CONTEXT OUTPUT] llm_context_keys:", list(llm_context.keys()) if isinstance(llm_context, dict) else [])
    print("[CONTEXT OUTPUT] full_context_keys:", list(structured_context.keys()) if isinstance(structured_context, dict) else [])

    return {
        "llm_context": llm_context,
        
        "full_context": {
        **structured_context,
        "table_samples": table_samples,
    },
    }


# ------------------------------------------
# SQL GENERATION NODE
# ------------------------------------------
def sql_generation_node(state: AgentState) -> Dict[str, Any]:
    context = state.get("llm_context", {})

    print("\n=== NODE: sql_generation ===")
    print("[SQL_GENERATION INPUT] query:", context.get("query", ""))
    print("[SQL_GENERATION INPUT] tables:", context.get("tables", []))
    print("[SQL_GENERATION INPUT] selected_columns:", context.get("selected_columns", {}))

    try:
        sql = generate_sql(context)

        print("[SQL_GENERATION OUTPUT] sql:\n", sql)

        return {
            "previous_sql": state.get("sql", ""),
            "sql": sql,
            "validation_error": "",
            "db_error": "",
        }

    except Exception as e:
        print("[SQL_GENERATION ERROR]:", str(e))
        return {
            "previous_sql": state.get("sql", ""),
            "sql": state.get("sql", ""),
            "validation_error": str(e),
            "db_error": "",
            "retry_count": state.get("retry_count", 0) + 1,
        }


# ------------------------------------------
# SQL VALIDATION NODE
# ------------------------------------------
def sql_validation_node(state: AgentState) -> Dict[str, Any]:
    sql = state.get("sql", "")
    context = state.get("llm_context", {})

    print("\n=== NODE: sql_validation ===")
    print("[SQL_VALIDATION INPUT] sql:\n", sql)

    if not str(sql).strip():
        error_message = state.get("validation_error", "Generated SQL is empty.")
        print("[SQL_VALIDATION ERROR]:", error_message)
        return {
            "validation_error": error_message,
        }

    is_valid, message = validate_sql(sql, context)

    print("[SQL_VALIDATION OUTPUT] is_valid:", is_valid)
    print("[SQL_VALIDATION OUTPUT] message:", message)

    if is_valid:
        return {"validation_error": ""}

    return {
        "validation_error": message,
        "retry_count": state.get("retry_count", 0) + 1,
    }


# ------------------------------------------
# SQL EXECUTION NODE
# ------------------------------------------
def sql_execution_node(state: AgentState) -> Dict[str, Any]:
    sql = state.get("sql", "")

    print("\n=== NODE: sql_execution ===")
    print("[SQL_EXECUTION INPUT] sql:\n", sql)

    raw_result = execute_sql(sql)
    db_result = _normalize_db_result(raw_result)

    print("[SQL_EXECUTION OUTPUT] row_count:", db_result.get("row_count", 0))
    print("[SQL_EXECUTION OUTPUT] columns:", db_result.get("columns", []))
    print("[SQL_EXECUTION OUTPUT] error:", db_result.get("error"))

    if db_result["error"]:
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
    context = state.get("llm_context", {})
    previous_sql = state.get("sql", "")
    validation_error = state.get("validation_error", "")
    db_error = state.get("db_error", "")
    combined_error = validation_error or db_error or "Unknown SQL correction error"

    print("\n=== NODE: sql_correction ===")
    print("[SQL_CORRECTION INPUT] previous_sql:\n", previous_sql)
    print("[SQL_CORRECTION INPUT] validation_error:", validation_error)
    print("[SQL_CORRECTION INPUT] db_error:", db_error)

    try:
        corrected_sql = correct_sql(
            context=context,
            previous_sql=previous_sql,
            error=combined_error,
        )

        print("[SQL_CORRECTION OUTPUT] corrected_sql:\n", corrected_sql)

        return {
            "sql": corrected_sql,
            "validation_error": "",
            "db_error": "",
        }

    except Exception as e:
        print("[SQL_CORRECTION ERROR]:", str(e))
        return {
            "validation_error": str(e),
            "retry_count": state.get("retry_count", 0) + 1,
        }


# ------------------------------------------
# RESULT NODE
# ------------------------------------------
def result_reasoning_node(state: AgentState) -> Dict[str, Any]:
    intent = state.get("intent", "irrelevant")
    mode = state.get("mode", "lookup")
    db_result = state.get("db_result", {})

    print("\n=== NODE: result_reasoning ===")
    print("[RESULT INPUT] intent:", intent)
    print("[RESULT INPUT] mode:", mode)
    print("[RESULT INPUT] db_row_count:", db_result.get("row_count", 0) if isinstance(db_result, dict) else 0)

    if intent == "irrelevant":
        print("[RESULT OUTPUT] response: fallback message for irrelevant intent")
        structured = {
            "explanation": FALLBACK_QUERY_ERROR_MESSAGE,
            "rows": [],
            "columns": [],
            "table_text": "",
        }
        return {"response": structured}

    if db_result.get("error") or not db_result.get("rows"):
        validation_error = (state.get("validation_error") or "").strip()
        db_error = (state.get("db_error") or "").strip()

        # Always return a structured fallback so the UI can render consistently
        structured = {
            "explanation": FALLBACK_QUERY_ERROR_MESSAGE,
            "rows": [],
            "columns": [],
            "table_text": "",
        }

        if validation_error:
            print("[RESULT OUTPUT] validation_error:", validation_error)
            return {"response": structured}

        if db_error:
            print("[RESULT OUTPUT] db_error:", db_error)
            return {"response": structured}

        print("[RESULT OUTPUT] response: fallback message for empty data")
        return {"response": structured}

    if mode == "reasoning":
        response_text = reason_over_result(
            query=state.get("query", ""),
            result=db_result,
            context=state.get("full_context", {}),
        )
        print("[RESULT OUTPUT] reasoning response:\n", response_text)

        structured = {
            "explanation": response_text,
            "rows": db_result.get("rows", []),
            "columns": db_result.get("columns", []),
            "table_text": format_table_view(db_result.get("rows", []), db_result.get("columns", [])) if db_result.get("rows") and db_result.get("columns") else "",
        }

        return {"response": structured}

    response = process_result(db_result, state.get("query", ""))
    print("[RESULT OUTPUT] lookup response:\n", response)

    # process_result already returns a structured dict on success,
    # or a fallback string on error. Normalize to structured form.
    if isinstance(response, dict):
        return {"response": response}

    structured = {
        "explanation": response if isinstance(response, str) else FALLBACK_QUERY_ERROR_MESSAGE,
        "rows": db_result.get("rows", []),
        "columns": db_result.get("columns", []),
        "table_text": format_table_view(db_result.get("rows", []), db_result.get("columns", [])) if db_result.get("rows") and db_result.get("columns") else "",
    }

    return {"response": structured}


# ------------------------------------------
# CONDITIONAL EDGES
# ------------------------------------------
def should_continue_after_routing(state: AgentState) -> str:
    route = "irrelevant" if state.get("intent") == "irrelevant" else "continue"
    print("\n[EDGE] should_continue_after_routing ->", route)
    return route


def should_retry_after_validation(state: AgentState) -> str:
    has_validation_error = bool((state.get("validation_error") or "").strip())
    if not has_validation_error:
        print("\n[EDGE] should_retry_after_validation -> execute")
        return "execute"

    retry_count = state.get("retry_count", 0)
    max_retries = state.get("max_retries", 5)
    route = "correction" if retry_count < max_retries else "finish"
    print(f"\n[EDGE] should_retry_after_validation -> {route} (retry_count={retry_count}, max_retries={max_retries})")
    return route


def should_retry_after_execution(state: AgentState) -> str:
    has_db_error = bool((state.get("db_error") or "").strip())
    if not has_db_error:
        print("\n[EDGE] should_retry_after_execution -> finish")
        return "finish"

    retry_count = state.get("retry_count", 0)
    max_retries = state.get("max_retries", 5)
    route = "correction" if retry_count < max_retries else "finish"
    print(f"\n[EDGE] should_retry_after_execution -> {route} (retry_count={retry_count}, max_retries={max_retries})")
    return route
