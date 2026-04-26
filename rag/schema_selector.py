# ==========================================
# Schema Selector
# ==========================================

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Set, Tuple

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
    value = _normalize_text(intent or "")
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


def _normalize_table_name(raw_name: str, available_tables: List[str]) -> Optional[str]:
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

    candidate = _normalize_text(raw_name).replace("-", "_")
    candidate = re.sub(r"\s+", " ", candidate)

    if candidate in alias_map:
        mapped = alias_map[candidate]
        if mapped in available_tables:
            return mapped

    candidate_key = candidate.replace(" ", "_")
    if candidate_key in available_map:
        return available_map[candidate_key]

    if candidate in available_map:
        return available_map[candidate]

    return None


def _normalize_table_names(raw_names: List[str], available_tables: List[str]) -> List[str]:
    normalized: List[str] = []

    for raw_name in raw_names:
        table_name = _normalize_table_name(raw_name, available_tables)
        if table_name:
            normalized.append(table_name)

    return _dedupe_keep_order(normalized)


def _filter_schema_tables_by_allowlist(
    schema_tables: Dict[str, Any],
    available_schema: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Restrict schema_docs tables to tables present in actual DB schema,
    using case-insensitive matching.
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


def _build_table_search_text(table_name: str, metadata: Dict[str, Any]) -> str:
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


def _query_flags(query: str) -> Dict[str, bool]:
    query_norm = _normalize_text(query)

    return {
        "has_login": "login" in query_norm,
        "has_logout": "logout" in query_norm or "logoff" in query_norm,
        "has_leave": "leave" in query_norm,

       
        "has_details": any(token in query_norm for token in [
            "details", "detail", "full", "complete", "information", "show"
        ]),

        "has_reason": any(token in query_norm for token in ["reason", "why", "explain"]),
        "has_policy": any(token in query_norm for token in ["policy", "rule"]),
        "has_approval": any(token in query_norm for token in ["approval", "approved"]),
        "has_half_day": "half day" in query_norm or "half-day" in query_norm,
        "has_permission": "permission" in query_norm,
        "has_lop": "lop" in query_norm or "loss of pay" in query_norm,
        "has_hours": "hours" in query_norm,
        "has_minutes": "minutes" in query_norm,
        "has_shift": "shift" in query_norm,
        "has_holiday": "holiday" in query_norm or "weekoff" in query_norm,
        "has_monthly": "month" in query_norm or "monthly" in query_norm,
        "has_total": any(token in query_norm for token in ["total", "sum", "count"]),
    }


def _special_case_selection(
    query: str,
    intent: str,
    schema_tables: Dict[str, Any],
) -> Optional[List[str]]:
    """
    Hard minimal-first rules for the most common HRMS question shapes.
    These rules are intentionally stronger than LLM freedom.
    """
    flags = _query_flags(query)
    query_norm = _normalize_text(query)

    # Hard override: operational login/logout questions should stay in login_mast.
    if (flags["has_login"] or flags["has_logout"]) and "leave" not in query_norm:
        if "login_mast" in schema_tables:
            return ["login_mast"]

    # Explicit login/logout facts -> login_mast only
    if flags["has_login"] and flags["has_logout"] and not flags["has_reason"] and not flags["has_leave"]:
        return [table for table in ["login_mast"] if table in schema_tables]

    # Worked hours/minutes -> login_mast only
    if (flags["has_hours"] or flags["has_minutes"]) and not flags["has_leave"] and not flags["has_reason"]:
        return [table for table in ["login_mast"] if table in schema_tables]

    # Simple attendance lookup -> login_mast only
    if intent == "attendance" and not flags["has_leave"] and not flags["has_reason"] and not flags["has_policy"]:
        return [table for table in ["login_mast"] if table in schema_tables]

    # If attendance question mentions leave/half-day/permission, include both attendance and leave
    if intent == "attendance" and (flags["has_leave"] or flags["has_half_day"] or flags["has_permission"] or flags["has_holiday"]):
        tables = []
        for t in ["login_mast", "emp_leave_setting"]:
            if t in schema_tables:
                tables.append(t)
        return _dedupe_keep_order(tables)

    # Daily leave / status / weekoff / permission -> emp_leave_setting first
    # FIXED LEAVE SELECTION
    if intent == "leave":

        base = []

        # Always include base table
        if "emp_leave_setting" in schema_tables:
            base.append("emp_leave_setting")

        # CRITICAL FIX: "leave details"
        if flags["has_details"]:
            if "Leave_detail" in schema_tables:
                base.append("Leave_detail")

        # Explicit fields needing details
        if any(token in _normalize_text(query) for token in [
            "type", "reason", "apply", "applied"
        ]):
            if "Leave_detail" in schema_tables:
                base.append("Leave_detail")

        # Half-day / approval → leave_dates
        if flags["has_approval"] or flags["has_half_day"]:
            if "leave_dates" in schema_tables:
                base.append("leave_dates")

        return _dedupe_keep_order(base)

    # Explanation / why absent / half-day / LOP / permission reasoning
    if intent == "attendance_explanation":
        tables: List[str] = []

        for table in ["login_mast", "emp_leave_setting"]:
            if table in schema_tables:
                tables.append(table)

        if flags["has_shift"]:
            for table in ["shift_details", "emp_default_shift", "trnEmployeeWeeklyShift"]:
                if table in schema_tables:
                    tables.append(table)

        if flags["has_holiday"]:
            for table in ["holiday_master", "trnCandidateHolidayMapping"]:
                if table in schema_tables:
                    tables.append(table)

        if flags["has_lop"] or flags["has_permission"] or flags["has_monthly"]:
            if "cl_detail" in schema_tables:
                tables.append("cl_detail")

        if flags["has_leave"] or flags["has_half_day"] or flags["has_approval"]:
            for table in ["Leave_detail", "leave_dates"]:
                if table in schema_tables:
                    tables.append(table)

        return _dedupe_keep_order(tables)

    # Policy question
    if intent == "policy":
        tables: List[str] = []

        for table in ["mstCLPolicyRule", "trnExceptionEmployeeCLPolicy", "mstWeekoffType"]:
            if table in schema_tables:
                tables.append(table)

        if flags["has_shift"] and "shift_details" in schema_tables:
            tables.append("shift_details")

        if flags["has_lop"] or flags["has_permission"]:
            if "cl_detail" in schema_tables:
                tables.append("cl_detail")

        return _dedupe_keep_order(tables)

    return None


def _score_table(
    query: str,
    intent: str,
    table_name: str,
    metadata: Dict[str, Any],
) -> int:
    score = 0
    query_norm = _normalize_text(query)
    query_tokens = _tokenize(query)
    metadata_text = _build_table_search_text(table_name, metadata)
    metadata_tokens = _tokenize(metadata_text)

    overlap = query_tokens.intersection(metadata_tokens)
    score += len(overlap) * 3

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
        "permission": {"cl_detail", "emp_leave_setting"},
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
    special_case = _special_case_selection(query, intent, schema_tables)
    if special_case:
        return special_case

    ranked = _rank_tables(query, intent, schema_tables)

    if intent == "attendance":
        limit = 1
    elif intent == "leave":
        limit = 3
    elif intent == "attendance_explanation":
        limit = 6
    elif intent == "policy":
        limit = 5
    else:
        limit = 1

    selected = ranked[:limit]

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


def _extract_json_from_text(text: str) -> Optional[Dict[str, Any]]:
    if not text:
        return None

    raw = text.strip()

    # fenced block
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, flags=re.DOTALL | re.IGNORECASE)
    if match:
        raw = match.group(1)

    # plain json object
    if not raw.startswith("{"):
        brace_match = re.search(r"(\{.*\})", raw, flags=re.DOTALL)
        if brace_match:
            raw = brace_match.group(1)

    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _call_selector_llm(
    query: str,
    intent: str,
    schema_tables: Dict[str, Any],
) -> Tuple[List[str], Dict[str, List[str]]]:
    """
    LLM-based semantic selector.

    Returns:
        (
            selected_tables: list[str],
            selected_columns: dict[str, list[str]]
        )
    """
    llm = get_llm("router")
    if llm is None:
        return [], {}

    schema_summary = _build_llm_schema_summary(schema_tables)
    available_tables = list(schema_tables.keys())

    prompt = f"""
        You are an expert HRMS schema selector.

        Your job is to choose the MINIMUM REQUIRED tables and columns to answer the user query.

        Core principles:
        - Select the smallest useful schema context.
        - Prefer one table when one table is enough.
        - Avoid joins unless the user question requires evidence from multiple tables.
        - Prefer operational fact/status tables over reference tables.
        - Do not invent table names.
        - Do not invent column names.
        - Return only tables and columns present in AVAILABLE SCHEMA.

        USER QUERY:
        {query}

        INTENT:
        {intent}

        AVAILABLE SCHEMA:
        {schema_summary}

        HRMS SELECTION RULES:
        1. Login/logout, punch, worked-hours, and worked-minutes queries must use ONLY login_mast unless the user explicitly asks for leave, shift, policy, or explanation.
        2. Daily leave, weekoff, permission, LOP, or final day-status queries should use emp_leave_setting first.
        3. Add Leave_detail only when the query asks for leave type, reason, applied date, leave request, or application details.
        4. Add leave_dates only when the query asks for approval workflow, day-wise leave dates, or half-day split.
        5. Add shift_details only when the query asks about shift timing, late coming, expected hours, or shift comparison.
        6. Add cl_detail only when the query asks about monthly summary, CL balance, LOP total, permission total, payroll-style totals, or month-level reconciliation.
        7. Add holiday_master only when the query asks about holiday, weekoff/holiday conflict, or absence explanation involving a non-working day.
        8. For explanation queries, include only the evidence tables needed to explain the issue. Do not include all possible related tables.
        9. Avoid reference/policy tables unless the user asks about policy, rule, eligibility, limit, category, or restriction.
        10. Never select a table only because a join hint exists.

        RESPONSE FORMAT:
        Return valid JSON only in this exact shape:
        {{
        "tables": [
            {{
            "table": "login_mast",
            "columns": ["emp_id", "login_date", "login_time", "logoff_time"]
            }}
        ]
        }}

        NO extra explanation.
        NO markdown.
        NO comments.
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
        data = _extract_json_from_text(raw_output)
        if not data:
            return [], {}

        raw_tables = data.get("tables", [])
        if not isinstance(raw_tables, list):
            return [], {}

        selected_tables: List[str] = []
        selected_columns: Dict[str, List[str]] = {}

        for item in raw_tables:
            if not isinstance(item, dict):
                continue

            raw_table_name = str(item.get("table", "")).strip()
            normalized_table = _normalize_table_name(raw_table_name, available_tables)
            if not normalized_table:
                continue

            selected_tables.append(normalized_table)

            requested_columns = item.get("columns", [])
            real_columns = list((schema_tables.get(normalized_table, {}) or {}).get("columns", {}).keys())

            if isinstance(requested_columns, list):
                cleaned_columns = [
                    str(col).strip()
                    for col in requested_columns
                    if str(col).strip() in real_columns
                ]
                if cleaned_columns:
                    selected_columns[normalized_table] = _dedupe_keep_order(cleaned_columns)

        return _dedupe_keep_order(selected_tables), selected_columns

    except Exception:
        return [], {}


def _select_columns_for_table(
    query: str,
    intent: str,
    table_name: str,
    metadata: Dict[str, Any],
) -> List[str]:
    """
    Deterministically choose the most relevant columns for a selected table.
    This is used when LLM did not return columns or returned incomplete ones.
    """
    query_norm = _normalize_text(query)
    query_tokens = _tokenize(query)
    all_columns = list((metadata.get("columns") or {}).keys())
    selected: List[str] = []

    # Always try to include business keys first
    for key in metadata.get("business_keys", []):
        if key in all_columns:
            selected.append(key)

    # Table-specific minimal rules
    if table_name == "login_mast":
        for col in ["emp_id", "login_date", "login_time", "logoff_time", "shift_code", "Logintype"]:
            if col in all_columns:
                selected.append(col)

        if "minutes" in query_norm or "hours" in query_norm:
            for col in ["login_time", "logoff_time"]:
                if col in all_columns:
                    selected.append(col)

    elif table_name == "emp_leave_setting":
        for col in [
            "leave_id",
            "emp_id",
            "leave_date",
            "leave_status",
            "leave_remark",
            "LopCount",
            "isEmployeeCL",
            "EmpLop",
            "HODComments",
            "markedby",
            "isApproval",
            "previousStatus",
            "previousMarkedBy",
        ]:
            if col in all_columns:
                selected.append(col)

    elif table_name == "Leave_detail":
        for col in ["leave_id", "emp_id", "leav_type", "reason", "apply_date", "comp_date", "frmtime", "totime"]:
            if col in all_columns:
                selected.append(col)

    elif table_name == "leave_dates":
        for col in ["leave_id", "leave_date", "leave_day", "manager_appr", "hr_appr"]:
            if col in all_columns:
                selected.append(col)

    elif table_name == "shift_details":
        for col in ["shift_code", "shift_name", "shift_intime", "shift_outtime", "shift_restinterval"]:
            if col in all_columns:
                selected.append(col)

    elif table_name == "emp_default_shift":
        for col in ["emp_id", "shift_code", "last_update_date"]:
            if col in all_columns:
                selected.append(col)

    elif table_name == "trnEmployeeWeeklyShift":
        for col in ["euid", "shiftCode", "fromDate", "toDate"]:
            if col in all_columns:
                selected.append(col)

    elif table_name == "cl_detail":
        for col in [
            "emp_id",
            "emp_year",
            "emp_month",
            "CLavailed",
            "CLbalance",
            "LOP",
            "Permission",
            "holidays",
            "company_workingdays",
        ]:
            if col in all_columns:
                selected.append(col)

    # Query-token overlap
    for col in all_columns:
        if _normalize_text(col) in query_norm or _normalize_text(col).replace("_", " ") in query_norm:
            selected.append(col)
        elif _tokenize(col).intersection(query_tokens):
            selected.append(col)

    if not selected:
        selected = all_columns[: min(8, len(all_columns))]

    return _dedupe_keep_order([col for col in selected if col in all_columns])


def _build_selected_schema(
    schema_tables: Dict[str, Any],
    selected_tables: List[str],
    llm_selected_columns: Optional[Dict[str, List[str]]] = None,
    query: str = "",
    intent: str = "attendance",
) -> Dict[str, Any]:
    """
    Return selected schema with only the relevant columns preserved.
    """
    llm_selected_columns = llm_selected_columns or {}
    selected_schema: Dict[str, Any] = {}

    for table_name in selected_tables:
        metadata = schema_tables.get(table_name)
        if not isinstance(metadata, dict):
            continue

        metadata_copy = dict(metadata)
        real_columns = list((metadata.get("columns") or {}).keys())

        requested_columns = llm_selected_columns.get(table_name, [])
        cleaned_columns = [col for col in requested_columns if col in real_columns]

        if not cleaned_columns:
            cleaned_columns = _select_columns_for_table(
                query=query,
                intent=intent,
                table_name=table_name,
                metadata=metadata,
            )

        metadata_copy["columns"] = {
            col: metadata["columns"][col]
            for col in cleaned_columns
            if col in metadata.get("columns", {})
        }

        selected_schema[table_name] = metadata_copy

    return selected_schema


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

    Returns:
        list[str]
    """
    bundle = select_schema_bundle(
        query=query,
        intent=intent,
        available_schema=available_schema,
        use_llm=use_llm,
        schema_path=schema_path,
    )
    return bundle["selected_tables"]


def select_schema_bundle(
    query: str,
    intent: Optional[str] = None,
    available_schema: Optional[Dict[str, Any]] = None,
    use_llm: bool = True,
    schema_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Main production selector.

    Returns a structured bundle:
    {
        "query": str,
        "intent": str,
        "selected_tables": list[str],
        "selected_schema": dict,
        "selected_columns": dict[str, list[str]]
    }
    """
    clean_query = (query or "").strip()
    safe_intent = _safe_intent(intent)

    if not clean_query:
        fallback_schema = load_full_schema_document(schema_path=schema_path).get("tables", {})
        fallback_tables = ["login_mast"] if "login_mast" in fallback_schema else list(fallback_schema.keys())[:1]
        selected_schema = _build_selected_schema(
            schema_tables=fallback_schema,
            selected_tables=fallback_tables,
            query=clean_query,
            intent=safe_intent,
        )
        return {
            "query": clean_query,
            "intent": safe_intent,
            "selected_tables": fallback_tables,
            "selected_schema": selected_schema,
            "selected_columns": {
                table: list(meta.get("columns", {}).keys())
                for table, meta in selected_schema.items()
            },
        }

    schema_doc = load_full_schema_document(schema_path=schema_path)
    schema_tables = schema_doc.get("tables", {})

    schema_tables = _filter_schema_tables_by_allowlist(
        schema_tables=schema_tables,
        available_schema=available_schema,
    )

    if not schema_tables:
        raise SchemaLoaderError("No schema tables available for selection.")

    special_case = _special_case_selection(clean_query, safe_intent, schema_tables)
    llm_selected_tables: List[str] = []
    llm_selected_columns: Dict[str, List[str]] = {}

    if special_case:
        selected_tables = special_case
    else:
        if use_llm:
            llm_selected_tables, llm_selected_columns = _call_selector_llm(
                query=clean_query,
                intent=safe_intent,
                schema_tables=schema_tables,
            )

        selected_tables = llm_selected_tables or _select_top_tables_by_intent(
            query=clean_query,
            intent=safe_intent,
            schema_tables=schema_tables,
        )

    selected_tables = [table for table in selected_tables if table in schema_tables]

    if not selected_tables:
        selected_tables = ["login_mast"] if "login_mast" in schema_tables else list(schema_tables.keys())[:1]

    selected_tables = _dedupe_keep_order(selected_tables)

    selected_schema = _build_selected_schema(
        schema_tables=schema_tables,
        selected_tables=selected_tables,
        llm_selected_columns=llm_selected_columns,
        query=clean_query,
        intent=safe_intent,
    )

    selected_columns = {
        table_name: list((table_meta.get("columns") or {}).keys())
        for table_name, table_meta in selected_schema.items()
    }

    return {
        "query": clean_query,
        "intent": safe_intent,
        "selected_tables": selected_tables,
        "selected_schema": selected_schema,
        "selected_columns": selected_columns,
    }


def get_selected_schema(
    query: str,
    intent: Optional[str] = None,
    available_schema: Optional[Dict[str, Any]] = None,
    use_llm: bool = True,
    schema_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Convenience wrapper:
    return selected schema metadata with selected columns only.
    """
    bundle = select_schema_bundle(
        query=query,
        intent=intent,
        available_schema=available_schema,
        use_llm=use_llm,
        schema_path=schema_path,
    )
    return bundle["selected_schema"]


def get_schema_selection_debug(
    query: str,
    intent: Optional[str] = None,
    schema_path: Optional[str] = None,
    available_schema: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Debug helper for development.
    """
    safe_intent = _safe_intent(intent)
    schema_doc = load_full_schema_document(schema_path=schema_path)
    schema_tables = schema_doc.get("tables", {})
    schema_tables = _filter_schema_tables_by_allowlist(
        schema_tables=schema_tables,
        available_schema=available_schema,
    )

    ranked = _rank_tables(query, safe_intent, schema_tables)
    bundle = select_schema_bundle(
        query=query,
        intent=safe_intent,
        available_schema=available_schema,
        use_llm=True,
        schema_path=schema_path,
    )

    return {
        "query": query,
        "intent": safe_intent,
        "available_tables": get_table_names(schema_path=schema_path),
        "ranked_tables": ranked,
        "selected_tables": bundle["selected_tables"],
        "selected_columns": bundle["selected_columns"],
    }


# Backward-compatible alias
def schema_selector(query: str, intent: Optional[str] = None) -> List[str]:
    """
    Backward-compatible wrapper.
    """
    return select_relevant_schema(query=query, intent=intent)
