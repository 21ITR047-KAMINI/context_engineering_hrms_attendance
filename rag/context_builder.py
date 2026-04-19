# ==========================================
# Context Builder
# ==========================================

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List, Optional


VALID_INTENTS = {
    "attendance",
    "leave",
    "attendance_explanation",
    "policy",
    "irrelevant",
}


# ------------------------------------------
# HELPERS
# ------------------------------------------
def _normalize_intent(intent: Optional[str]) -> str:
    value = (intent or "").strip().lower()
    return value if value in VALID_INTENTS else "attendance"


def _dedupe_keep_order(items: List[str]) -> List[str]:
    seen = set()
    output: List[str] = []

    for item in items:
        cleaned = str(item).strip()
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            output.append(cleaned)

    return output


def _copy_schema(schema: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not schema:
        return {}
    return deepcopy(schema)


def _extract_join_hints_from_schema(schema: Dict[str, Any]) -> List[str]:
    join_hints: List[str] = []

    for _, table_meta in schema.items():
        if not isinstance(table_meta, dict):
            continue
        hints = table_meta.get("join_hints", [])
        if isinstance(hints, list):
            join_hints.extend(str(hint).strip() for hint in hints if str(hint).strip())

    return _dedupe_keep_order(join_hints)


def _extract_domains_from_schema(schema: Dict[str, Any]) -> List[str]:
    domains: List[str] = []

    for _, table_meta in schema.items():
        if not isinstance(table_meta, dict):
            continue
        domain = str(table_meta.get("domain", "")).strip()
        if domain:
            domains.append(domain)

    return _dedupe_keep_order(domains)


def _extract_table_summaries(schema: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """
    Create a clean per-table summary for prompt building and debugging.
    """
    summaries: Dict[str, Dict[str, Any]] = {}

    for table_name, table_meta in schema.items():
        if not isinstance(table_meta, dict):
            continue

        summaries[table_name] = {
            "domain": table_meta.get("domain", ""),
            "description": table_meta.get("description", ""),
            "primary_keys": deepcopy(table_meta.get("primary_keys", [])),
            "business_keys": deepcopy(table_meta.get("business_keys", [])),
            "column_names": list((table_meta.get("columns") or {}).keys()),
            "used_for": deepcopy(table_meta.get("used_for", [])),
            "join_hints": deepcopy(table_meta.get("join_hints", [])),
        }

    return summaries


def _build_business_focus(intent: str, tables: List[str]) -> List[str]:
    """
    High-level business focus areas inferred from intent + selected tables.
    This helps prompt builders frame what the model should care about.
    """
    focus: List[str] = []

    if intent == "attendance":
        focus.extend([
            "attendance event lookup",
            "login/logout interpretation",
            "shift-aware attendance understanding",
        ])

    elif intent == "leave":
        focus.extend([
            "leave status and workflow understanding",
            "employee leave application details",
            "day-wise leave validation",
        ])

    elif intent == "attendance_explanation":
        focus.extend([
            "attendance reasoning",
            "leave versus attendance reconciliation",
            "shift comparison and timing explanation",
            "holiday, permission, and LOP-aware interpretation",
        ])

    elif intent == "policy":
        focus.extend([
            "policy interpretation",
            "rule lookup",
            "employee-specific exception handling",
        ])

    # Table-driven focus
    table_focus_map = {
        "login_mast": "attendance facts",
        "emp_leave_setting": "processed leave outcome",
        "Leave_detail": "leave application details",
        "leave_dates": "date-wise leave approval",
        "shift_details": "shift timing reference",
        "emp_default_shift": "default employee shift",
        "trnEmployeeWeeklyShift": "date-range shift override",
        "cl_detail": "monthly leave balance and LOP summary",
        "emp_compoff": "comp-off validation",
        "holiday_master": "holiday applicability",
        "trnCandidateHolidayMapping": "employee holiday applicability",
        "mstEmployeeStatutoryLeave": "statutory leave evidence",
        "mstLeaveStatusStatutory": "statutory leave policy reference",
        "mstCLPolicyRule": "generic CL policy",
        "trnExceptionEmployeeCLPolicy": "employee-specific CL override",
        "mstWeekoffType": "weekoff rule reference",
        "pay_mst_category": "category-level attendance and leave policy",
        "mstRestrictLeaveMarkingCategory": "leave restriction controls",
    }

    for table in tables:
        if table in table_focus_map:
            focus.append(table_focus_map[table])

    return _dedupe_keep_order(focus)


def _build_query_analysis(query: str, intent: str) -> Dict[str, Any]:
    """
    Lightweight structured analysis of the user query.
    """
    query_lower = (query or "").strip().lower()

    is_why_question = any(
        token in query_lower
        for token in ["why", "reason", "explain", "how come", "what caused"]
    )

    is_policy_question = any(
        token in query_lower
        for token in ["policy", "rule", "allowed", "eligibility", "limit"]
    )

    is_lookup_question = not (is_why_question or is_policy_question)

    keywords = []
    tracked_keywords = [
        "attendance",
        "login",
        "logout",
        "leave",
        "shift",
        "holiday",
        "weekoff",
        "late",
        "absent",
        "half day",
        "lop",
        "permission",
        "compoff",
        "statutory",
        "policy",
        "rule",
    ]

    for token in tracked_keywords:
        if token in query_lower:
            keywords.append(token)

    return {
        "intent": intent,
        "is_why_question": is_why_question,
        "is_policy_question": is_policy_question,
        "is_lookup_question": is_lookup_question,
        "keywords": _dedupe_keep_order(keywords),
    }


def _build_retrieval_summary(
    tables: List[str],
    schema: Dict[str, Any],
    rules: List[str],
    join_hints: List[str],
) -> Dict[str, Any]:
    """
    Compact retrieval metadata for logging/debugging/UI use.
    """
    total_columns = 0
    domains = _extract_domains_from_schema(schema)

    for _, meta in schema.items():
        if isinstance(meta, dict):
            total_columns += len(meta.get("columns", {}) or {})

    return {
        "selected_table_count": len(tables),
        "selected_tables": deepcopy(tables),
        "selected_domains": domains,
        "total_selected_columns": total_columns,
        "rule_count": len(rules),
        "join_hint_count": len(join_hints),
    }


def _build_llm_schema_block(schema: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build an LLM-friendly schema block, preserving all relevant metadata
    needed by prompt builders.
    """
    tables_block: Dict[str, Any] = {}

    for table_name, meta in schema.items():
        if not isinstance(meta, dict):
            continue

        tables_block[table_name] = {
            "domain": meta.get("domain", ""),
            "description": meta.get("description", ""),
            "primary_keys": deepcopy(meta.get("primary_keys", [])),
            "business_keys": deepcopy(meta.get("business_keys", [])),
            "columns": deepcopy(meta.get("columns", {})),
            "used_for": deepcopy(meta.get("used_for", [])),
            "join_hints": deepcopy(meta.get("join_hints", [])),
        }

    return {
        "tables": tables_block
    }


# ------------------------------------------
# PUBLIC FUNCTION
# ------------------------------------------
def build_context(
    query: str,
    intent: str,
    schema: Dict[str, Any],
    rules: List[str],
    additional_join_hints: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Build structured working context for the LLM pipeline.

    This is the core RAG assembly layer:
    - query
    - intent
    - selected tables
    - full selected schema metadata
    - business rules
    - join hints
    - lightweight query analysis
    - compact retrieval summary

    Output shape:
    {
        "query": "...",
        "intent": "attendance_explanation",
        "tables": [...],
        "schema": {...},
        "rules": [...],
        "join_hints": [...],
        "table_summaries": {...},
        "query_analysis": {...},
        "business_focus": [...],
        "retrieval_summary": {...},
        "llm_context": {...}
    }
    """
    clean_query = (query or "").strip()
    safe_intent = _normalize_intent(intent)
    schema_copy = _copy_schema(schema)

    selected_tables = list(schema_copy.keys())
    rules_clean = _dedupe_keep_order([str(rule).strip() for rule in rules if str(rule).strip()])

    schema_join_hints = _extract_join_hints_from_schema(schema_copy)
    extra_join_hints = _dedupe_keep_order(
        [str(hint).strip() for hint in (additional_join_hints or []) if str(hint).strip()]
    )
    join_hints = _dedupe_keep_order(schema_join_hints + extra_join_hints)

    table_summaries = _extract_table_summaries(schema_copy)
    query_analysis = _build_query_analysis(clean_query, safe_intent)
    business_focus = _build_business_focus(safe_intent, selected_tables)
    retrieval_summary = _build_retrieval_summary(
        tables=selected_tables,
        schema=schema_copy,
        rules=rules_clean,
        join_hints=join_hints,
    )
    llm_schema_block = _build_llm_schema_block(schema_copy)

    context = {
        "query": clean_query,
        "intent": safe_intent,
        "tables": deepcopy(selected_tables),
        "schema": schema_copy,
        "rules": deepcopy(rules_clean),
        "join_hints": deepcopy(join_hints),
        "table_summaries": table_summaries,
        "query_analysis": query_analysis,
        "business_focus": business_focus,
        "retrieval_summary": retrieval_summary,
        "llm_context": {
            "query": clean_query,
            "intent": safe_intent,
            "tables": deepcopy(selected_tables),
            "schema": llm_schema_block["tables"],
            "rules": deepcopy(rules_clean),
            "join_hints": deepcopy(join_hints),
            "business_focus": deepcopy(business_focus),
        },
    }

    return context