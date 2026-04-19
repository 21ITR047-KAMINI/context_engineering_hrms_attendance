# ==========================================
# Schema Selector
# ==========================================

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set

from llm.provider import get_llm
from rag.schema_loader import (
    SchemaLoaderError,
    get_table_names,
    load_full_schema_document,
    load_schema,
)


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
def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _tokenize(text: str) -> Set[str]:
    return set(re.findall(r"[a-zA-Z_]+", _normalize_text(text)))


def _safe_intent(intent: Optional[str]) -> str:
    intent_value = _normalize_text(intent or "")
    return intent_value if intent_value in VALID_INTENTS else "attendance"


def _dedupe_keep_order(items: List[str]) -> List[str]:
    seen = set()
    output = []
    for item in items:
        cleaned = str(item).strip()
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            output.append(cleaned)
    return output


def _normalize_table_names(raw_names: List[str], available_tables: List[str]) -> List[str]:
    """
    Normalize LLM-returned table names against actual tables in schema_docs.json.
    Handles small variants such as:
    - leave_detail -> Leave_detail
    - leave_details -> Leave_detail
    - login mast -> login_mast
    """
    available_map = {table.lower(): table for table in available_tables}

    alias_map = {
        "leave_detail": "Leave_detail",
        "leave_details": "Leave_detail",
        "leave detail": "Leave_detail",
        "leave details": "Leave_detail",
        "login mast": "login_mast",
        "loginmast": "login_mast",
        "employee weekly shift": "trnEmployeeWeeklyShift",
        "weekly shift": "trnEmployeeWeeklyShift",
        "default shift": "emp_default_shift",
        "shift detail": "shift_details",
        "shift details": "shift_details",
        "cl details": "cl_detail",
        "cl detail": "cl_detail",
        "cl policy": "mstCLPolicyRule",
        "weekoff type": "mstWeekoffType",
    }

    normalized: List[str] = []

    for name in raw_names:
        candidate = _normalize_text(name).replace("-", "_")
        candidate = re.sub(r"\s+", " ", candidate)

        if candidate in alias_map:
            mapped = alias_map[candidate]
            if mapped in available_tables:
                normalized.append(mapped)
            continue

        candidate_key = candidate.replace(" ", "_")
        if candidate_key in available_map:
            normalized.append(available_map[candidate_key])
            continue

        if candidate in available_map:
            normalized.append(available_map[candidate])
            continue

    return _dedupe_keep_order(normalized)


def _build_table_search_text(table_name: str, metadata: Dict[str, Any]) -> str:
    """
    Build searchable text blob from every meaningful field present in schema_docs.json.
    This ensures all information is considered during rule scoring.
    """
    parts: List[str] = [table_name]

    for key, value in metadata.items():
        if isinstance(value, str):
            parts.append(value)
        elif isinstance(value, list):
            parts.extend(str(item) for item in value)
        elif isinstance(value, dict):
            for sub_key, sub_value in value.items():
                parts.append(str(sub_key))
                parts.append(str(sub_value))
        else:
            parts.append(str(value))

    return _normalize_text(" ".join(parts))


def _score_table(
    query: str,
    intent: str,
    table_name: str,
    metadata: Dict[str, Any],
) -> int:
    """
    Heuristic score using all schema metadata:
    - description
    - domain
    - columns
    - used_for
    - join_hints
    - keys
    """
    score = 0
    query_norm = _normalize_text(query)
    query_tokens = _tokenize(query)
    metadata_text = _build_table_search_text(table_name, metadata)
    metadata_tokens = _tokenize(metadata_text)

    # Token overlap from all metadata
    overlap = query_tokens.intersection(metadata_tokens)
    score += len(overlap) * 3

    # Domain-aware boosting
    domain = _normalize_text(str(metadata.get("domain", "")))
    used_for = " ".join(metadata.get("used_for", []))
    description = _normalize_text(str(metadata.get("description", "")))
    join_hints = " ".join(metadata.get("join_hints", []))
    columns = " ".join(metadata.get("columns", {}).keys())

    combined = f"{domain} {used_for} {description} {join_hints} {columns}"

    if intent == "attendance":
        if table_name == "login_mast":
            score += 20
        if "attendance" in combined or "login" in combined or "logout" in combined:
            score += 10
        if "shift" in query_norm and "shift" in combined:
            score += 6

    elif intent == "leave":
        if table_name in {"emp_leave_setting", "Leave_detail", "leave_dates"}:
            score += 18
        if "leave" in combined:
            score += 10
        if "approval" in query_norm and ("approval" in combined or "appr" in combined):
            score += 6

    elif intent == "attendance_explanation":
        if table_name in {
            "login_mast",
            "emp_leave_setting",
            "Leave_detail",
            "leave_dates",
            "shift_details",
            "cl_detail",
        }:
            score += 16
        if "reason" in query_norm or "why" in query_norm or "explain" in query_norm:
            if "used_for" in metadata or "reason" in combined or "explanation" in combined:
                score += 4
        if "holiday" in query_norm and table_name == "holiday_master":
            score += 12
        if "shift" in query_norm and table_name in {"shift_details", "emp_default_shift", "trnEmployeeWeeklyShift"}:
            score += 10
        if "lop" in query_norm or "salary" in query_norm or "permission" in query_norm:
            if table_name == "cl_detail":
                score += 12

    elif intent == "policy":
        if table_name in {
            "mstCLPolicyRule",
            "trnExceptionEmployeeCLPolicy",
            "mstWeekoffType",
            "cl_detail",
            "shift_details",
        }:
            score += 15
        if "policy" in combined or "rule" in combined:
            score += 10
        if "weekoff" in query_norm and table_name == "mstWeekoffType":
            score += 8

    # Important query words
    keyword_boosts = {
        "login": {"login_mast"},
        "logout": {"login_mast"},
        "attendance": {"login_mast", "cl_detail"},
        "leave": {"emp_leave_setting", "Leave_detail", "leave_dates"},
        "shift": {"shift_details", "emp_default_shift", "trnEmployeeWeeklyShift"},
        "holiday": {"holiday_master"},
        "compoff": {"emp_compoff"},
        "statutory": {"mstEmployeeStatutoryLeave", "mstLeaveStatusStatutory"},
        "weekoff": {"mstWeekoffType"},
        "policy": {"mstCLPolicyRule", "trnExceptionEmployeeCLPolicy"},
        "lop": {"cl_detail", "emp_leave_setting"},
        "permission": {"cl_detail"},
    }

    for word, boosted_tables in keyword_boosts.items():
        if word in query_norm and table_name in boosted_tables:
            score += 8

    return score


def _rank_tables(query: str, intent: str, schema_tables: Dict[str, Any]) -> List[str]:
    scored = []
    for table_name, metadata in schema_tables.items():
        score = _score_table(query, intent, table_name, metadata)
        if score > 0:
            scored.append((table_name, score))

    scored.sort(key=lambda item: item[1], reverse=True)
    return [table_name for table_name, _ in scored]


def _select_top_tables_by_intent(query: str, intent: str, schema_tables: Dict[str, Any]) -> List[str]:
    ranked = _rank_tables(query, intent, schema_tables)

    if intent == "attendance":
        limit = 2
    elif intent == "leave":
        limit = 3
    elif intent == "attendance_explanation":
        limit = 6
    elif intent == "policy":
        limit = 5
    else:
        limit = 1

    selected = ranked[:limit]

    # Safe intent-aware fallback
    if not selected:
        if intent == "attendance":
            selected = ["login_mast"]
        elif intent == "leave":
            selected = ["emp_leave_setting", "Leave_detail", "leave_dates"]
        elif intent == "attendance_explanation":
            selected = ["login_mast", "emp_leave_setting", "shift_details", "cl_detail"]
        elif intent == "policy":
            selected = ["mstCLPolicyRule", "mstWeekoffType"]
        else:
            selected = ["login_mast"]

    return [table for table in selected if table in schema_tables]


def _build_llm_schema_summary(schema_tables: Dict[str, Any]) -> str:
    """
    Compact but complete schema summary using all important fields in schema_docs.json.
    """
    parts = []

    for table_name, metadata in schema_tables.items():
        columns = ", ".join(metadata.get("columns", {}).keys())
        primary_keys = ", ".join(metadata.get("primary_keys", []))
        business_keys = ", ".join(metadata.get("business_keys", []))
        used_for = ", ".join(metadata.get("used_for", []))
        join_hints = "; ".join(metadata.get("join_hints", []))

        parts.append(
            f"""Table: {table_name}
Domain: {metadata.get("domain", "")}
Description: {metadata.get("description", "")}
Primary Keys: {primary_keys}
Business Keys: {business_keys}
Columns: {columns}
Used For: {used_for}
Join Hints: {join_hints}
"""
        )

    return "\n".join(parts)


def _call_selector_llm(query: str, intent: str, schema_tables: Dict[str, Any]) -> List[str]:
    """
    Optional LLM-based semantic selector.
    Returns normalized table names if available, else [].
    """
    llm = get_llm("router")

    if llm is None:
        return []

    schema_summary = _build_llm_schema_summary(schema_tables)
    available_tables = list(schema_tables.keys())

    prompt = f"""
You are an expert HRMS schema selector.

Task:
Select the minimum relevant database tables required to answer the user query.

User Query:
{query}

Intent:
{intent}

Available Schema:
{schema_summary}

Rules:
1. Use meaning, not keyword matching only.
2. Prefer minimal tables.
3. For simple attendance queries, prefer login_mast.
4. For leave queries, prefer emp_leave_setting, Leave_detail, leave_dates as needed.
5. For explanation queries, include attendance + leave + shift + balance/policy tables only if required.
6. Return only table names from the available schema.
7. No explanation.

Output format:
Comma-separated table names only.
Example:
login_mast, shift_details
""".strip()

    try:
        response = llm.invoke(prompt)

        if isinstance(response, str):
            raw_output = response
        else:
            raw_output = getattr(response, "content", "") or ""

        if isinstance(raw_output, list):
            raw_output = " ".join(str(item) for item in raw_output)

        raw_output = str(raw_output).strip()

        if not raw_output:
            return []

        raw_names = [part.strip() for part in raw_output.split(",") if part.strip()]
        return _normalize_table_names(raw_names, available_tables)

    except Exception:
        return []


def _filter_schema_tables_by_allowlist(
    schema_tables: Dict[str, Any],
    available_schema: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Restrict schema_docs.json tables to only tables present in available_schema,
    using case-insensitive matching.

    Example:
    - schema_docs.json has "Leave_detail"
    - DB schema allowlist has "leave_detail"
    -> keep the schema_docs.json entry
    """
    if not available_schema:
        return schema_tables

    allowlist_map = {
        str(table_name).strip().lower(): table_name
        for table_name in available_schema.keys()
        if str(table_name).strip()
    }

    filtered: Dict[str, Any] = {}
    for table_name, metadata in schema_tables.items():
        if str(table_name).strip().lower() in allowlist_map:
            filtered[table_name] = metadata

    return filtered


# ------------------------------------------
# PUBLIC FUNCTIONS
# ------------------------------------------
def select_relevant_schema(
    query: str,
    intent: Optional[str] = None,
    available_schema: Optional[Dict[str, Any]] = None,
    use_llm: bool = True,
    schema_path: Optional[str] = None,
) -> List[str]:
    """
    Select relevant table names for a user query.

    Strategy:
    1. Load full schema metadata from schema_docs.json
    2. Consider every field from each table's metadata
    3. Try LLM semantic table selection
    4. Fall back to robust heuristic scoring
    5. Return minimal table set in priority order

    Args:
        query: user query
        intent: attendance / leave / attendance_explanation / policy / irrelevant
        available_schema: optional external schema map; if provided, acts as allowlist
        use_llm: whether to try LLM selection first
        schema_path: optional custom schema_docs.json path

    Returns:
        list[str]: selected table names
    """
    clean_query = (query or "").strip()
    safe_intent = _safe_intent(intent)

    if not clean_query:
        return ["login_mast"]

    schema_doc = load_full_schema_document(schema_path=schema_path)
    schema_tables = schema_doc.get("tables", {})

    # Restrict selection to tables present in available_schema using
    # case-insensitive matching.
    schema_tables = _filter_schema_tables_by_allowlist(
        schema_tables=schema_tables,
        available_schema=available_schema,
    )

    if not schema_tables:
        raise SchemaLoaderError("No schema tables available for selection.")

    selected_tables: List[str] = []

    # LLM-first selection
    if use_llm:
        selected_tables = _call_selector_llm(
            query=clean_query,
            intent=safe_intent,
            schema_tables=schema_tables,
        )

    # Heuristic fallback or supplement
    if not selected_tables:
        selected_tables = _select_top_tables_by_intent(
            query=clean_query,
            intent=safe_intent,
            schema_tables=schema_tables,
        )

    # Ensure selected tables really exist
    selected_tables = [table for table in selected_tables if table in schema_tables]

    if not selected_tables:
        return ["login_mast"] if "login_mast" in schema_tables else list(schema_tables.keys())[:1]

    return _dedupe_keep_order(selected_tables)


def get_selected_schema(
    query: str,
    intent: Optional[str] = None,
    available_schema: Optional[Dict[str, Any]] = None,
    use_llm: bool = True,
    schema_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Convenience wrapper:
    select tables first, then return full metadata for selected tables.
    """
    selected_tables = select_relevant_schema(
        query=query,
        intent=intent,
        available_schema=available_schema,
        use_llm=use_llm,
        schema_path=schema_path,
    )

    return load_schema(
        table_names=selected_tables,
        schema_path=schema_path,
        include_meta=False,
        strict=True,
    )


def get_schema_selection_debug(
    query: str,
    intent: Optional[str] = None,
    schema_path: Optional[str] = None,
    available_schema: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Debug helper for development.
    Shows ranking and final selection.
    """
    safe_intent = _safe_intent(intent)
    schema_doc = load_full_schema_document(schema_path=schema_path)
    schema_tables = schema_doc.get("tables", {})
    schema_tables = _filter_schema_tables_by_allowlist(
        schema_tables=schema_tables,
        available_schema=available_schema,
    )

    ranked = _rank_tables(query, safe_intent, schema_tables)
    selected = select_relevant_schema(
        query=query,
        intent=safe_intent,
        available_schema=available_schema,
        use_llm=False,
        schema_path=schema_path,
    )

    return {
        "query": query,
        "intent": safe_intent,
        "available_tables": get_table_names(schema_path=schema_path),
        "ranked_tables": ranked,
        "selected_tables": selected,
    }


# Backward-compatible alias
def schema_selector(query: str, intent: Optional[str] = None) -> List[str]:
    """
    Backward-compatible wrapper.
    """
    return select_relevant_schema(query=query, intent=intent)