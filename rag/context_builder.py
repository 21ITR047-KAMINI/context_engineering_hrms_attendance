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


def _extract_selected_columns(schema: Dict[str, Any]) -> Dict[str, List[str]]:
    selected_columns: Dict[str, List[str]] = {}

    for table_name, table_meta in schema.items():
        if not isinstance(table_meta, dict):
            continue

        columns = table_meta.get("columns", {})
        if isinstance(columns, dict):
            selected_columns[table_name] = list(columns.keys())
        else:
            selected_columns[table_name] = []

    return selected_columns


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

    keywords: List[str] = []
    tracked_keywords = [
        "attendance",
        "login",
        "logout",
        "logoff",
        "leave",
        "shift",
        "holiday",
        "weekoff",
        "week off",
        "late",
        "absent",
        "half day",
        "half-day",
        "lop",
        "permission",
        "compoff",
        "statutory",
        "policy",
        "rule",
        "hours",
        "minutes",
        "worked",
        "working",
        "count",
        "total",
        "summary",
        "month",
        "monthly",
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


def _build_business_focus(intent: str, tables: List[str], query_analysis: Dict[str, Any]) -> List[str]:
    """
    High-level business focus areas inferred from intent + selected tables + query shape.
    This helps prompt builders frame what the model should care about.
    """
    focus: List[str] = []
    keywords = query_analysis.get("keywords", [])

    if intent == "attendance":
        focus.extend([
            "attendance event lookup",
            "login/logout interpretation",
            "worked-time computation",
        ])

    elif intent == "leave":
        focus.extend([
            "processed leave/day-status interpretation",
            "employee leave application details",
            "date-wise leave validation",
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

    if "hours" in keywords or "minutes" in keywords:
        focus.append("worked time calculation")

    if "lop" in keywords:
        focus.append("loss of pay reasoning")

    if "permission" in keywords:
        focus.append("permission reasoning")

    if "half day" in keywords or "half-day" in keywords:
        focus.append("half-day interpretation")

    if "month" in keywords or "monthly" in keywords or "summary" in keywords:
        focus.append("monthly summary analysis")

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


def _build_query_guidance(
    intent: str,
    tables: List[str],
    query_analysis: Dict[str, Any],
) -> List[str]:
    """
    Build practical guidance for the prompt builder / LLM context.
    These are not business rules from the domain file, but contextual guidance
    derived from the selected schema and query shape.
    """
    guidance: List[str] = []
    keywords = query_analysis.get("keywords", [])
    table_set = set(tables)

    guidance.append("Use the minimum number of selected tables required to answer the question correctly.")
    guidance.append("Use ONLY the selected schema tables and columns; never invent or rename schema elements.")
    guidance.append("Do not change user-provided literal filters such as dates, employee IDs, or numeric IDs.")

    if len(tables) == 1:
        guidance.append("Only one table is selected, so do not create joins.")
        guidance.append("Single-table-first strategy applies: avoid JOIN unless explicitly required by selected schema.")

    if "login_mast" in table_set and "login" in keywords and ("logout" in keywords or "logoff" in keywords):
        guidance.append("This is a login/logout style query, so login_mast is likely sufficient.")

    if "login_mast" in table_set and ("hours" in keywords or "minutes" in keywords):
        guidance.append("For worked-hours or worked-minutes queries, calculate from login_time and logoff_time in login_mast unless a precomputed operational field is explicitly requested.")

    if "emp_leave_setting" in table_set and "leave" in keywords:
        guidance.append("emp_leave_setting is the primary processed leave/day-status layer for simple leave queries.")

    if "Leave_detail" in table_set:
        guidance.append("Leave_detail should be used for leave type, reason, application, and time-range details.")

    if "leave_dates" in table_set:
        guidance.append("leave_dates should be used only for day-wise leave coverage, half-day value, or approval workflow details.")

    if "cl_detail" in table_set:
        guidance.append("cl_detail is best for monthly totals, balances, permissions, holidays, and LOP summaries, not raw punch facts.")

    if "shift_details" in table_set:
        guidance.append("shift_details is useful only when expected timing, shift hours, weekoff, or lateness must be interpreted.")

    if "attendance_explanation" == intent:
        guidance.append("This is an explanation query, so reconcile processed leave/day-status, raw attendance facts, and supporting shift or summary evidence before concluding.")

    if "policy" == intent:
        guidance.append("This is a policy query, so prefer policy/reference interpretation over transactional proof.")

    return _dedupe_keep_order(guidance)


def _build_retrieval_summary(
    tables: List[str],
    schema: Dict[str, Any],
    rules: List[str],
    join_hints: List[str],
    selected_columns: Dict[str, List[str]],
) -> Dict[str, Any]:
    """
    Compact retrieval metadata for logging/debugging/UI use.
    """
    total_columns = 0
    domains = _extract_domains_from_schema(schema)

    for table_name, columns in selected_columns.items():
        total_columns += len(columns)

    return {
        "selected_table_count": len(tables),
        "selected_tables": deepcopy(tables),
        "selected_domains": domains,
        "selected_columns": deepcopy(selected_columns),
        "total_selected_columns": total_columns,
        "rule_count": len(rules),
        "join_hint_count": len(join_hints),
    }


def _build_llm_schema_block(schema: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build an LLM-friendly schema block, preserving only relevant metadata
    for prompt builders.
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

    return {"tables": tables_block}


def _build_result_preferences(intent: str, query_analysis: Dict[str, Any]) -> Dict[str, Any]:
    """
    Lightweight hinting for downstream response formatting.
    """
    keywords = query_analysis.get("keywords", [])
    return {
        "prefer_reasoning": bool(query_analysis.get("is_why_question")) or intent in {"attendance_explanation", "policy"},
        "prefer_tabular": intent in {"attendance", "leave"} and not query_analysis.get("is_why_question", False),
        "is_aggregate": any(token in keywords for token in ["count", "total", "summary", "month", "monthly", "hours", "minutes"]),
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
    - selected schema metadata (already column-filtered)
    - business rules
    - join hints
    - query analysis
    - business focus
    - retrieval summary
    - query guidance
    - result preferences
    - llm_context
    """
    clean_query = (query or "").strip()
    safe_intent = _normalize_intent(intent)
    schema_copy = _copy_schema(schema)

    selected_tables = list(schema_copy.keys())
    selected_columns = _extract_selected_columns(schema_copy)

    rules_clean = _dedupe_keep_order(
        [str(rule).strip() for rule in rules if str(rule).strip()]
    )

    schema_join_hints = _extract_join_hints_from_schema(schema_copy)
    extra_join_hints = _dedupe_keep_order(
        [str(hint).strip() for hint in (additional_join_hints or []) if str(hint).strip()]
    )
    join_hints = _dedupe_keep_order(schema_join_hints + extra_join_hints)

    table_summaries = _extract_table_summaries(schema_copy)
    query_analysis = _build_query_analysis(clean_query, safe_intent)
    business_focus = _build_business_focus(safe_intent, selected_tables, query_analysis)
    query_guidance = _build_query_guidance(safe_intent, selected_tables, query_analysis)
    retrieval_summary = _build_retrieval_summary(
        tables=selected_tables,
        schema=schema_copy,
        rules=rules_clean,
        join_hints=join_hints,
        selected_columns=selected_columns,
    )
    llm_schema_block = _build_llm_schema_block(schema_copy)
    result_preferences = _build_result_preferences(safe_intent, query_analysis)

    context = {
        "query": clean_query,
        "intent": safe_intent,
        "tables": deepcopy(selected_tables),
        "selected_columns": deepcopy(selected_columns),
        "schema": schema_copy,
        "rules": deepcopy(rules_clean),
        "join_hints": deepcopy(join_hints),
        "table_summaries": table_summaries,
        "query_analysis": query_analysis,
        "business_focus": business_focus,
        "query_guidance": query_guidance,
        "result_preferences": result_preferences,
        "retrieval_summary": retrieval_summary,
        "llm_context": {
            "query": clean_query,
            "intent": safe_intent,
            "tables": deepcopy(selected_tables),
            "selected_columns": deepcopy(selected_columns),
            "schema": llm_schema_block["tables"],
            "rules": deepcopy(rules_clean),
            "join_hints": deepcopy(join_hints),
            "business_focus": deepcopy(business_focus),
            "query_analysis": deepcopy(query_analysis),
            "query_guidance": deepcopy(query_guidance),
            "result_preferences": deepcopy(result_preferences),
        },
    }

    return context
