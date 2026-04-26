# ==========================================
# Result Processor
# ==========================================

from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

from constants import FALLBACK_QUERY_ERROR_MESSAGE
from tools.result_tool import format_table_view


# ------------------------------------------
# HELPERS
# ------------------------------------------
def _safe_str(value: Any) -> str:
    if value is None:
        return "null"
    return str(value)


def _normalize_db_result(db_result: Any) -> Dict[str, Any]:
    """
    Normalize DB result into a stable structure.

    Expected output:
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

    if db_result is None:
        normalized["error"] = "No result returned."
        return normalized

    if isinstance(db_result, dict):
        rows = db_result.get("rows", [])
        columns = db_result.get("columns", [])
        error = db_result.get("error")

        if not isinstance(rows, list):
            rows = []
        if not isinstance(columns, list):
            columns = []

        normalized["rows"] = rows
        normalized["columns"] = columns
        normalized["error"] = error
        normalized["row_count"] = len(rows)
        return normalized

    normalized["error"] = f"Unexpected DB result format: {type(db_result).__name__}"
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

    for idx, row in enumerate(rows, start=1):
        records.append({"row_number": idx, "value": row})

    return records


def _format_table(rows: List[Any], columns: List[str], max_rows: int = 20) -> str:
    """
    Create a readable plain-text table.
    """
    if not rows:
        return "Data not found"

    records = _rows_to_records(rows, columns)
    if not records:
        return "Data not found"

    preview_records = records[:max_rows]

    all_columns: List[str] = []
    if columns:
        all_columns = [str(col) for col in columns]
    else:
        seen = set()
        for record in preview_records:
            for key in record.keys():
                if key not in seen:
                    seen.add(key)
                    all_columns.append(str(key))

    if not all_columns:
        return "Data not found"

    # Compute widths
    widths = {}
    for col in all_columns:
        widths[col] = len(col)

    for record in preview_records:
        for col in all_columns:
            widths[col] = max(widths[col], len(_safe_str(record.get(col))))

    header = " | ".join(col.ljust(widths[col]) for col in all_columns)
    separator = "-+-".join("-" * widths[col] for col in all_columns)

    lines = [header, separator]

    for record in preview_records:
        line = " | ".join(_safe_str(record.get(col)).ljust(widths[col]) for col in all_columns)
        lines.append(line)

    if len(records) > max_rows:
        lines.append(f"... {len(records) - max_rows} more row(s) omitted.")

    return "\n".join(lines)


def _detect_patterns(records: List[Dict[str, Any]]) -> List[str]:
    """
    Detect basic HR/attendance patterns from returned records.
    This stays lightweight and deterministic.
    """
    insights: List[str] = []

    if not records:
        return insights

    missing_login_found = False
    missing_logout_found = False
    late_found = False
    lop_found = False
    leave_found = False
    holiday_found = False
    permission_found = False

    for record in records:
        login_time = record.get("login_time")
        logoff_time = record.get("logoff_time")
        is_late = record.get("isLateComing")
        lop_count = record.get("LopCount", record.get("LOP"))
        leave_status = record.get("leave_status")
        holidays = record.get("holidays")
        permission = record.get("Permission")

        if "login_time" in record and login_time in (None, "", "null"):
            missing_login_found = True

        if "logoff_time" in record and logoff_time in (None, "", "null"):
            missing_logout_found = True

        if is_late not in (None, "", "null", 0, "0", False, "False"):
            late_found = True

        if lop_count not in (None, "", "null", 0, "0", 0.0, "0.0", False, "False"):
            lop_found = True

        if leave_status not in (None, "", "null"):
            leave_found = True

        if holidays not in (None, "", "null", 0, "0", 0.0, "0.0", False, "False"):
            holiday_found = True

        if permission not in (None, "", "null", 0, "0", 0.0, "0.0", False, "False"):
            permission_found = True

    if missing_login_found:
        insights.append("Missing login was found in the returned attendance evidence.")
    if missing_logout_found:
        insights.append("Missing logout was found in the returned attendance evidence.")
    if late_found:
        insights.append("Late attendance indicators are present in the returned records.")
    if lop_found:
        insights.append("Loss of pay related values are present in the returned records.")
    if leave_found:
        insights.append("Leave-related status information is present in the returned records.")
    if holiday_found:
        insights.append("Holiday-related values are present in the returned records.")
    if permission_found:
        insights.append("Permission-related values are present in the returned records.")

    return insights


def _build_summary(query: Optional[str], records: List[Dict[str, Any]], columns: List[str]) -> str:
    """
    Build a short deterministic summary for lookup-mode responses.
    """
    if not records:
        return "Data not found"

    row_count = len(records)

    if row_count == 1:
        first = records[0]
        important_fields = [
            "emp_id",
            "login_date",
            "leave_date",
            "login_time",
            "logoff_time",
            "leave_status",
            "leave_remark",
            "shift_code",
            "LopCount",
            "LOP",
        ]

        parts = []
        for field in important_fields:
            if field in first and first.get(field) not in (None, "", "null"):
                parts.append(f"{field}={_safe_str(first.get(field))}")

        if parts:
            return "Matched 1 record: " + ", ".join(parts) + "."
        return "Matched 1 record."

    if query:
        return f"Matched {row_count} records for query: {query}"

    return f"Matched {row_count} records."


# ------------------------------------------
# PUBLIC FUNCTION
# ------------------------------------------
def process_result(db_result: Dict[str, Any], query: Optional[str] = None) -> Union[str, Dict[str, Any]]:
    """
    Process DB result for lookup-mode responses.

    Returns:
        str

    Behavior:
    - DB error -> "Data not found"
    - empty rows -> "Data not found"
    - otherwise -> summary + optional detected patterns + formatted table
    """
    try:
        normalized = _normalize_db_result(db_result)

        if normalized.get("error"):
            return FALLBACK_QUERY_ERROR_MESSAGE

        rows = normalized.get("rows", [])
        columns = normalized.get("columns", [])

        if not rows:
            return FALLBACK_QUERY_ERROR_MESSAGE

        records = _rows_to_records(rows, columns)
        if not records:
            return FALLBACK_QUERY_ERROR_MESSAGE

        summary = _build_summary(query, records, columns)
        patterns = _detect_patterns(records)
        table_text = format_table_view(rows, columns)

        parts: List[str] = [summary]

        if patterns:
            parts.append("Detected Insights:")
            parts.extend(f"- {item}" for item in patterns)

        explanation = "\n\n".join(parts)

        return {
            "explanation": explanation,
            "rows": rows,
            "columns": columns,
            "table_text": table_text,
        }

    except Exception:
        return FALLBACK_QUERY_ERROR_MESSAGE
