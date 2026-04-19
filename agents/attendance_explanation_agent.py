# ==========================================
# Attendance Explanation Agent
# ==========================================

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from llm.provider import get_llm


# ------------------------------------------
# HELPERS
# ------------------------------------------
def _safe_to_str(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, (dict, list, tuple)):
        try:
            return json.dumps(value, default=str, ensure_ascii=False)
        except Exception:
            return str(value)
    return str(value)


def _normalize_db_result(result: Any) -> Dict[str, Any]:
    """
    Normalize DB result to:
    {
        "rows": [...],
        "columns": [...],
        "error": None | str,
        "row_count": int
    }
    """
    normalized = {
        "rows": [],
        "columns": [],
        "error": None,
        "row_count": 0,
    }

    if result is None:
        normalized["error"] = "No result returned."
        return normalized

    if isinstance(result, dict):
        rows = result.get("rows", [])
        columns = result.get("columns", [])
        error = result.get("error")

        if rows is None:
            rows = []
        if columns is None:
            columns = []

        normalized["rows"] = rows if isinstance(rows, list) else []
        normalized["columns"] = columns if isinstance(columns, list) else []
        normalized["error"] = error
        normalized["row_count"] = len(normalized["rows"])
        return normalized

    normalized["error"] = f"Unexpected DB result format: {type(result).__name__}"
    return normalized


def _rows_to_records(rows: List[Any], columns: List[str]) -> List[Dict[str, Any]]:
    """
    Convert rows + columns into record dictionaries when possible.
    Supports:
    - list[dict]
    - list[list/tuple] with columns
    """
    records: List[Dict[str, Any]] = []

    if not rows:
        return records

    first = rows[0]

    if isinstance(first, dict):
        for row in rows:
            if isinstance(row, dict):
                records.append(dict(row))
        return records

    if columns and isinstance(first, (list, tuple)):
        for row in rows:
            if isinstance(row, (list, tuple)):
                record = {}
                for idx, col in enumerate(columns):
                    record[col] = row[idx] if idx < len(row) else None
                records.append(record)
        return records

    # Fallback for unknown row shape
    for idx, row in enumerate(rows, start=1):
        records.append({"row_number": idx, "value": row})

    return records


def _select_relevant_fields(record: Dict[str, Any]) -> Dict[str, Any]:
    """
    Keep the most explanation-relevant fields first, then append others.
    """
    priority_fields = [
        "emp_id",
        "login_date",
        "leave_date",
        "login_time",
        "logoff_time",
        "shift_code",
        "shift_name",
        "shift_intime",
        "shift_outtime",
        "leave_status",
        "leave_remark",
        "reason",
        "leav_type",
        "leave_day",
        "manager_appr",
        "hr_appr",
        "LopCount",
        "EmpLop",
        "LOP",
        "Permission",
        "holidays",
        "weekOffName",
        "holidayTypeName",
        "HODComments",
        "markedby",
        "previousStatus",
        "previousMarkedBy",
        "isApproval",
    ]

    selected: Dict[str, Any] = {}

    for field in priority_fields:
        if field in record:
            selected[field] = record[field]

    for key, value in record.items():
        if key not in selected:
            selected[key] = value

    return selected


def _build_evidence_block(records: List[Dict[str, Any]], max_records: int = 5) -> str:
    """
    Convert result records into a concise evidence block for the LLM.
    """
    if not records:
        return "No evidence rows available."

    lines: List[str] = []
    limited_records = records[:max_records]

    for idx, record in enumerate(limited_records, start=1):
        focused_record = _select_relevant_fields(record)
        lines.append(f"Record {idx}:")
        for key, value in focused_record.items():
            lines.append(f"- {key}: {_safe_to_str(value)}")

    if len(records) > max_records:
        lines.append(f"... {len(records) - max_records} more record(s) omitted for brevity.")

    return "\n".join(lines)


def _build_rule_block(context: Dict[str, Any], max_rules: int = 20) -> str:
    rules = context.get("rules", [])
    if not isinstance(rules, list) or not rules:
        return "No business rules available."

    limited_rules = [str(rule).strip() for rule in rules if str(rule).strip()][:max_rules]
    return "\n".join(f"- {rule}" for rule in limited_rules)


def _build_table_block(context: Dict[str, Any]) -> str:
    tables = context.get("tables", [])
    if not isinstance(tables, list) or not tables:
        return "No tables available."
    return ", ".join(str(table) for table in tables)


def _build_join_hint_block(context: Dict[str, Any], max_hints: int = 15) -> str:
    join_hints = context.get("join_hints", [])
    if not isinstance(join_hints, list) or not join_hints:
        return "No join hints available."

    limited_hints = [str(hint).strip() for hint in join_hints if str(hint).strip()][:max_hints]
    return "\n".join(f"- {hint}" for hint in limited_hints)


def _build_query_analysis_block(context: Dict[str, Any]) -> str:
    analysis = context.get("query_analysis", {})
    if not isinstance(analysis, dict) or not analysis:
        return "No query analysis available."

    lines = []
    for key, value in analysis.items():
        lines.append(f"- {key}: {_safe_to_str(value)}")
    return "\n".join(lines)


def _build_explanation_prompt(
    query: str,
    result: Dict[str, Any],
    context: Dict[str, Any],
) -> str:
    """
    Build a robust explanation prompt grounded in:
    - user query
    - retrieved result evidence
    - selected schema/tables
    - business rules
    - join hints
    """
    records = _rows_to_records(
        rows=result.get("rows", []),
        columns=result.get("columns", []),
    )

    evidence_block = _build_evidence_block(records)
    rules_block = _build_rule_block(context)
    tables_block = _build_table_block(context)
    join_block = _build_join_hint_block(context)
    analysis_block = _build_query_analysis_block(context)

    prompt = f"""
You are an expert HRMS attendance and leave reasoning analyst.

Your job is to explain the answer to the user ONLY from the provided evidence.
Do not invent facts. Do not assume missing values. If evidence is incomplete, say so clearly.

USER QUERY:
{query}

SELECTED TABLES:
{tables_block}

QUERY ANALYSIS:
{analysis_block}

BUSINESS RULES:
{rules_block}

JOIN HINTS:
{join_block}

DATABASE RESULT EVIDENCE:
{evidence_block}

INSTRUCTIONS:
1. Answer the user's actual question directly.
2. Use the evidence first, then apply business rules carefully.
3. If the question is a "why" question, explain the most likely supported reason.
4. If leave, holiday, weekoff, shift timing, permission, or LOP could affect the answer, mention them only when supported by evidence.
5. If records are conflicting, mention the conflict instead of forcing certainty.
6. If evidence is insufficient, say what is missing.
7. Keep the answer concise but meaningful.
8. Do not output SQL.
9. Do not output JSON.
10. Do not mention internal system design.

OUTPUT STYLE:
- Human-readable
- 2 to 6 lines
- Grounded in the provided data
""".strip()

    return prompt


def _fallback_explanation(query: str, result: Dict[str, Any], context: Dict[str, Any]) -> str:
    """
    Non-LLM fallback explanation when model call fails.
    """
    records = _rows_to_records(
        rows=result.get("rows", []),
        columns=result.get("columns", []),
    )

    if not records:
        return "No evidence was found to explain the result."

    first = records[0]
    pieces: List[str] = []

    if "leave_status" in first:
        pieces.append(f"leave_status={_safe_to_str(first.get('leave_status'))}")
    if "leave_remark" in first and first.get("leave_remark"):
        pieces.append(f"leave_remark={_safe_to_str(first.get('leave_remark'))}")
    if "login_time" in first:
        pieces.append(f"login_time={_safe_to_str(first.get('login_time'))}")
    if "logoff_time" in first:
        pieces.append(f"logoff_time={_safe_to_str(first.get('logoff_time'))}")
    if "shift_intime" in first:
        pieces.append(f"shift_intime={_safe_to_str(first.get('shift_intime'))}")
    if "shift_outtime" in first:
        pieces.append(f"shift_outtime={_safe_to_str(first.get('shift_outtime'))}")
    if "LopCount" in first:
        pieces.append(f"LopCount={_safe_to_str(first.get('LopCount'))}")
    if "LOP" in first:
        pieces.append(f"LOP={_safe_to_str(first.get('LOP'))}")
    if "Permission" in first:
        pieces.append(f"Permission={_safe_to_str(first.get('Permission'))}")
    if "holidays" in first:
        pieces.append(f"holidays={_safe_to_str(first.get('holidays'))}")

    if not pieces:
        return (
            "Relevant records were found, but a detailed explanation could not be generated. "
            "Please review the returned attendance, leave, and shift evidence."
        )

    return f"Based on the available evidence for '{query}', the key factors are: " + ", ".join(pieces) + "."


# ------------------------------------------
# PUBLIC FUNCTION
# ------------------------------------------
def reason_over_result(
    query: str,
    result: Dict[str, Any],
    context: Dict[str, Any],
    llm: Optional[Any] = None,
) -> str:
    """
    Build a grounded explanation from:
    - user query
    - normalized DB result
    - structured RAG context

    This function is the active reasoning path used by graph/nodes.py.
    """
    clean_query = (query or "").strip()
    normalized_result = _normalize_db_result(result)
    context = context if isinstance(context, dict) else {}

    if not clean_query:
        return "No query provided for explanation."

    if normalized_result.get("error"):
        return "Data not found"

    if normalized_result.get("row_count", 0) == 0:
        return "Data not found"

    explanation_llm = llm or get_llm("explanation")

    prompt = _build_explanation_prompt(
        query=clean_query,
        result=normalized_result,
        context=context,
    )

    try:
        if explanation_llm is None:
            return _fallback_explanation(clean_query, normalized_result, context)

        if hasattr(explanation_llm, "invoke"):
            response = explanation_llm.invoke(prompt)

            if isinstance(response, str):
                answer = response.strip()
            else:
                content = getattr(response, "content", "")
                if isinstance(content, list):
                    answer = " ".join(str(item) for item in content).strip()
                else:
                    answer = str(content).strip()

            if answer:
                return answer

        if hasattr(explanation_llm, "predict"):
            answer = explanation_llm.predict(prompt)
            if isinstance(answer, str) and answer.strip():
                return answer.strip()

        if callable(explanation_llm):
            answer = explanation_llm(prompt)
            if isinstance(answer, str) and answer.strip():
                return answer.strip()

    except Exception:
        pass

    return _fallback_explanation(clean_query, normalized_result, context)


# ------------------------------------------
# LEGACY COMPATIBILITY WRAPPER
# ------------------------------------------
def create_attendance_explanation_agent(llm: Any, tools: Any):
    """
    Legacy compatibility wrapper.

    This project now uses graph/nodes.py + reason_over_result(...)
    as the active flow. This wrapper remains only so older imports
    do not break immediately.
    """

    def agent_node(state: Dict[str, Any]) -> Dict[str, Any]:
        query = state.get("query", "")
        result = (
            state.get("db_result")
            or state.get("result")
            or {"rows": [], "columns": [], "error": "No db_result provided."}
        )
        context = (
            state.get("full_context")
            or state.get("context")
            or state.get("llm_context")
            or {}
        )

        response = reason_over_result(
            query=query,
            result=result,
            context=context,
            llm=llm,
        )
        return {"response": response}

    return agent_node
