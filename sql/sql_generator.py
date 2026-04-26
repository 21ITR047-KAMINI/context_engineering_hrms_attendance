# ==========================================
# SQL Generator (Production-Ready)
# ==========================================

from __future__ import annotations

import re
from typing import Any, Dict, List, Set

from llm.provider import get_llm


# ------------------------------------------
# RESPONSE NORMALIZATION
# ------------------------------------------
def _extract_text_from_response(response: Any) -> str:
    if response is None:
        return ""

    if isinstance(response, str):
        return response

    content = getattr(response, "content", None)

    if isinstance(content, str):
        return content

    if isinstance(content, list):
        parts: List[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                parts.append(str(item.get("text", "")))
            else:
                parts.append(str(item))
        return "\n".join(parts)

    return str(response)


# ------------------------------------------
# SQL CLEANING
# ------------------------------------------
def clean_sql(response_text: str) -> str:
    sql = (response_text or "").strip()

    if not sql:
        return ""

    match = re.search(r"```(?:sql)?\s*(.*?)```", sql, flags=re.IGNORECASE | re.DOTALL)
    if match:
        sql = match.group(1).strip()

    sql = re.sub(r"^\s*sql\s*", "", sql, flags=re.IGNORECASE).strip()
    sql = sql.strip("`").strip()

    return sql


def _normalize_sql_server_syntax(sql: str) -> str:
    if not sql:
        return ""

    normalized = re.sub(
        r"\bDATE\s*\(\s*([a-zA-Z_][a-zA-Z0-9_\.\[\]]*)\s*\)",
        r"CAST(\1 AS DATE)",
        sql,
        flags=re.IGNORECASE,
    )
    return normalized


# ------------------------------------------
# FEW-SHOT EXAMPLES
# ------------------------------------------
def _build_few_shot_examples() -> str:
    return """
EXAMPLE 1 (LOGIN & LOGOUT FOR SPECIFIC DATE):
Question: Show login and logout for employee on a specific date
SQL:
SELECT emp_id, login_date, login_time, logoff_time
FROM login_mast
WHERE emp_id = 'AD25061070'
  AND CAST(login_date AS DATE) = '2026-04-02';

EXAMPLE 2 (TOTAL WORKED HOURS - MONTHLY):
Question: Total worked hours for March 2026
SQL:
SELECT emp_id,
       SUM(DATEDIFF(SECOND, login_time, logoff_time)) / 3600.0 AS total_hours
FROM login_mast
WHERE emp_id = 'AD25061070'
  AND login_date >= '2026-03-01'
  AND login_date < '2026-04-01'
GROUP BY emp_id;

EXAMPLE 3 (LEAVE DETAILS SIMPLE):
Question: Show leave details for employee
SQL:
SELECT emp_id, leave_date, leave_status, leave_remark
FROM emp_leave_setting
WHERE emp_id = 'AD25061070'
ORDER BY leave_date;

EXAMPLE 4 (LEAVE DETAILS WITH TYPE):
Question: Show detailed leave info (type, reason)
SQL:
SELECT els.emp_id, els.leave_date, ld.leav_type, ld.reason
FROM emp_leave_setting els
JOIN Leave_detail ld ON els.leave_id = ld.leave_id
WHERE els.emp_id = 'AD25061070';

EXAMPLE 5 (CL VS LOP IDENTIFICATION):
Question: Show CL and LOP
SQL:
SELECT emp_id, leave_date, leave_status, leave_remark,
       CASE
           WHEN leave_remark LIKE '%No Balance%' THEN 'LOP'
           ELSE 'CL/Leave'
       END AS leave_type
FROM emp_leave_setting
WHERE emp_id = 'AD25061070'
  AND leave_status = 'F';

EXAMPLE 6 (MONTH-WISE WORKING MINUTES):
Question: Month-wise working minutes (2025)
SQL:
SELECT emp_id,
       YEAR(login_date) AS year,
       MONTH(login_date) AS month,
       SUM(DATEDIFF(MINUTE, login_time, logoff_time)) AS total_minutes
FROM login_mast
WHERE emp_id = 'AD25061070'
  AND login_date >= '2025-01-01'
  AND login_date < '2026-01-01'
GROUP BY emp_id, YEAR(login_date), MONTH(login_date)
ORDER BY year, month;

EXAMPLE 7 (LEAVE COUNT FOR SPECIFIC DATE):
Question: Total leave on a specific date
SQL:
SELECT COUNT(*) AS total_leaves
FROM emp_leave_setting
WHERE emp_id = 'AD25061070'
  AND leave_date = '2026-03-02'
  AND leave_status = 'F';

EXAMPLE 8 (FULL ATTENDANCE FOR A MONTH):
Question: Full attendance with worked / leave / permission
SQL:
WITH dates AS (
    SELECT CAST('2026-03-01' AS DATE) AS dt
    UNION ALL
    SELECT DATEADD(DAY, 1, dt)
    FROM dates
    WHERE dt < '2026-03-31'
)
SELECT dt,
       lm.login_time,
       lm.logoff_time,
       els.leave_status,
       CASE
           WHEN els.leave_status = 'P' THEN 'Permission'
           WHEN els.leave_status = 'F' THEN 'Full Day Leave'
           WHEN els.leave_status = 'W' THEN 'Week Off'
           WHEN lm.login_time IS NOT NULL THEN 'Worked'
           ELSE 'Working Day'
       END AS status
FROM dates
LEFT JOIN login_mast lm
    ON lm.emp_id = 'AD25061070'
   AND CAST(lm.login_date AS DATE) = dt
LEFT JOIN emp_leave_setting els
    ON els.emp_id = 'AD25061070'
   AND CAST(els.leave_date AS DATE) = dt
OPTION (MAXRECURSION 31);

KEY LEARNINGS:
- Use login_mast for attendance facts
- Use emp_leave_setting for final day status
- Use Leave_detail only when type/reason is needed
- Avoid joins unless required
- No row in leave table can still mean working day
""".strip()

# ------------------------------------------
# QUERY ANALYSIS
# ------------------------------------------
def _extract_date_literals(text: str) -> Set[str]:
    return set(re.findall(r"\b\d{4}-\d{2}-\d{2}\b", text or ""))


def _infer_required_columns(query: str, context: Dict[str, Any]) -> List[str]:
    query_lower = (query or "").lower()
    required: List[str] = []

    tables = [str(t).lower() for t in context.get("tables", [])]

    if "login_mast" in tables:
        if "employee" in query_lower or "emp" in query_lower:
            required.append("emp_id")

        if "date" in query_lower or _extract_date_literals(query):
            required.append("login_date")

        asks_login = "login" in query_lower
        asks_logout = any(token in query_lower for token in ["logout", "logoff"])

        if asks_login:
            required.append("login_time")
        if asks_logout:
            required.append("logoff_time")

        if asks_login and asks_logout:
            for col in ["emp_id", "login_date", "login_time", "logoff_time"]:
                if col not in required:
                    required.append(col)

    if "emp_leave_setting" in tables:
        if "leave" in query_lower:
            required.extend(["emp_id", "leave_date", "leave_status"])

        if any(token in query_lower for token in ["remark", "reason", "lop", "cl"]):
            if "leave_remark" not in required:
                required.append("leave_remark")

    seen = set()
    ordered_required: List[str] = []
    for col in required:
        key = col.lower()
        if key not in seen:
            seen.add(key)
            ordered_required.append(col)

    return ordered_required


def _build_dynamic_planning_hints(query: str, context: Dict[str, Any]) -> str:
    query_lower = (query or "").lower()
    hints: List[str] = []

    if any(token in query_lower for token in ["login", "logout", "logoff", "attendance"]):
        hints.append("- Use login_mast for attendance facts.")
        hints.append("- For login/logout-by-date questions, include login_time and logoff_time.")
        hints.append("- If the user asks for the date too, include login_date.")

    if "leave" in query_lower:
        hints.append("- Use emp_leave_setting for leave status and final day status.")
        hints.append("- For simple leave lookup, avoid joining other tables.")

    if any(token in query_lower for token in ["reason", "type", "detail", "detailed"]):
        hints.append("- Use Leave_detail only when leave type/reason is explicitly requested.")

    if any(token in query_lower for token in ["month", "monthly", "year", "total", "sum", "hours", "minutes"]):
        hints.append("- Prefer SQL Server date boundaries: >= start_date and < next_period_start.")
        hints.append("- Use DATEDIFF with login_time and logoff_time for working duration calculations.")

    # If a month name is present without a 4-digit year, suggest using the current year
    month_match = re.search(r"\b(january|february|march|april|may|june|july|august|september|october|november|december)\b", query_lower)
    if month_match and not re.search(r"\b\d{4}\b", query_lower):
        from datetime import datetime
        current_year = datetime.now().year
        hints.append(f"- Use the current year ({current_year}) for month-only queries unless a year is specified.")

    if any(token in query_lower for token in ["full attendance", "calendar", "all days", "working day", "permission"]):
        hints.append("- For full month attendance status, use a recursive date CTE.")
        hints.append("- No row in leave table may still mean a normal working day.")

    if any(token in query_lower for token in ["cl", "lop", "no balance"]):
        hints.append("- Classify LOP using leave_remark LIKE '%No Balance%' when relevant.")

    required_columns = _infer_required_columns(query, context)
    if required_columns:
        hints.append(f"- Preserve required output columns: {required_columns}")

    if not hints:
        hints.append("- Keep SQL minimal and use the few-shot examples as the default pattern source.")

    return "\n".join(hints)
# ------------------------------------------
# BASIC VALIDATION
# ------------------------------------------
def _basic_sql_check(sql: str):
    if not sql:
        raise ValueError("SQL is empty")

    if not sql.lower().startswith(("select", "with")):
        raise ValueError("Only SELECT queries allowed")

    blocked = ["insert", "update", "delete", "drop", "alter", "truncate"]
    sql_lower = sql.lower()

    for b in blocked:
        if f" {b} " in f" {sql_lower} ":
            raise ValueError(f"Unsafe SQL detected: {b}")


# ------------------------------------------
# DOMAIN AND SCHEMA GUARDS
# ------------------------------------------
def _extract_tables_from_sql(sql: str) -> List[str]:
    matches = re.findall(r"\b(?:from|join)\s+([a-zA-Z0-9_\.\[\]]+)", sql, flags=re.IGNORECASE)
    tables: List[str] = []
    seen: Set[str] = set()

    for raw in matches:
        table = raw.strip().strip("[]")
        if "." in table:
            table = table.split(".")[-1].strip("[]")
        key = table.lower()
        if table and key not in seen:
            seen.add(key)
            tables.append(table)

    return tables


def _extract_selected_columns(sql: str) -> List[str]:
    if not sql:
        return []

    match = re.search(
        r"^\s*select\s+(.*?)\s+from\s",
        sql,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return []

    raw_select = match.group(1).strip()

    # simple split by comma; acceptable here because our generated queries are not highly nested
    pieces = [p.strip() for p in raw_select.split(",") if p.strip()]
    columns: List[str] = []

    for piece in pieces:
        piece = re.sub(r"\bas\s+[a-zA-Z_][a-zA-Z0-9_]*\b", "", piece, flags=re.IGNORECASE).strip()
        if "." in piece:
            piece = piece.split(".")[-1].strip()

        func_match = re.match(r"[a-zA-Z_][a-zA-Z0-9_]*\((.*?)\)$", piece)
        if func_match:
            inner = func_match.group(1).strip()
            if "." in inner:
                inner = inner.split(".")[-1].strip()
            if re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", inner):
                columns.append(inner.lower())
            continue

        if re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", piece):
            columns.append(piece.lower())

    return columns


def _enforce_domain_rules(sql: str, context: Dict[str, Any]):
    allowed_tables = {str(table).lower() for table in context.get("tables", [])}
    sql_tables = {table.lower() for table in _extract_tables_from_sql(sql)}

    if "login_mast" in sql_tables and "login_mast" not in allowed_tables:
        raise ValueError("SQL incorrectly switched to attendance domain")

    if "emp_leave_setting" in sql_tables and "emp_leave_setting" not in allowed_tables:
        raise ValueError("SQL incorrectly switched to leave domain")


def _enforce_schema_guards(sql: str, context: Dict[str, Any]):
    allowed_tables = {str(table).lower() for table in context.get("tables", [])}
    sql_tables = _extract_tables_from_sql(sql)

    if not sql_tables:
        raise ValueError("SQL must include at least one selected table")

    for table in sql_tables:
        if table.lower() not in allowed_tables:
            raise ValueError(f"SQL introduced non-selected table: {table}")

    if len(allowed_tables) == 1 and len(sql_tables) > 1:
        raise ValueError("Single-table query expected, but SQL introduced joins/multiple tables")

    query_dates = _extract_date_literals(str(context.get("query", "")))
    sql_dates = _extract_date_literals(sql)
    if query_dates and not query_dates.issubset(sql_dates):
        raise ValueError(f"SQL changed or dropped date literal(s). Expected at least: {sorted(query_dates)}")


def _enforce_required_columns(sql: str, context: Dict[str, Any]):
    required_columns = [c.lower() for c in _infer_required_columns(str(context.get("query", "")), context)]
    if not required_columns:
        return

    selected_columns = _extract_selected_columns(sql)
    if not selected_columns:
        return

    missing = [col for col in required_columns if col not in selected_columns]
    if missing:
        raise ValueError(f"SQL is missing required column(s): {missing}")


# ------------------------------------------
# PROMPTS
# ------------------------------------------
def build_sql_prompt(context: Dict[str, Any]) -> str:
    query = context.get("query", "")
    required_columns = _infer_required_columns(str(query), context)

    return f"""
You are a STRICT SQL Server query generator.

USER QUERY:
{query}

TABLES:
{context.get("tables")}

SELECTED COLUMNS BY TABLE:
{context.get("selected_columns")}

SCHEMA:
{context.get("schema")}

TABLE SAMPLE DATA:
{context.get("table_samples", {})}

SAMPLE DATA USAGE RULES:
1. Sample rows are only for understanding real column value formats.
2. Do not copy sample values unless the user asked for those exact values.
3. Preserve user-provided employee IDs and dates.
4. Use sample rows to understand column names, date formats, and status values.
5. If sample data conflicts with the user query, follow the user query.

GUIDELINES:
{context.get("query_guidance", [])}

BUSINESS RULES:
{context.get("rules", [])}

FEW-SHOT:
{_build_few_shot_examples()}

DYNAMIC PLANNING HINTS:
{_build_dynamic_planning_hints(str(query), context)}

REQUIRED OUTPUT COLUMNS:
{required_columns}

STRICT RULES:
INSTRUCTIONS:
1. Use ONLY the selected tables and columns shown above.
2. Use the minimum number of tables required to answer the question correctly.
3. Prefer precise joins using the provided join hints.
4. For attendance queries, use login_mast when attendance facts are needed.
5. For leave queries, use emp_leave_setting, Leave_detail, and leave_dates only as needed.
6. For explanation-heavy queries, still return SQL only; do not explain in this step.
7. If a date-specific answer is needed, make the SQL date-aware.
8. If monthly summary is required, use cl_detail when relevant.
9. Prefer readable aliases when helpful.
10. Use LEFT JOIN unless INNER JOIN is clearly required.
11. Do not use tables not present in the selected schema.
12. Do not invent columns.
13. Generate exactly one SQL statement.

**CRITICAL DATE RULE:**
- If user provides ONLY month and day (e.g., "march 24th", "december 25th") WITHOUT a year, you MUST use the year 2026.
- NEVER default to any other year like 2023, 2024, or 2025.
- Examples:
  - "march 24th" → Must be '2026-03-24'
  - "december 1" → Must be '2026-12-01'
  - "april 15" → Must be '2026-04-15'

SAFETY RULES:
- Output SQL only.
- No markdown.
- No code fences.
- No explanation.
- No comments.
- No INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, EXEC.
- Prefer SELECT only.
- If needed, a safe WITH clause followed by SELECT is allowed.
OUTPUT:
SQL ONLY
""".strip()


def build_correction_prompt(context: Dict[str, Any], sql: str, error: str) -> str:
    required_columns = _infer_required_columns(str(context.get("query", "")), context)

    return f"""
Fix this SQL strictly.

QUERY:
{context.get("query")}

TABLES:
{context.get("tables")}

SELECTED COLUMNS BY TABLE:
{context.get("selected_columns")}

SCHEMA:
{context.get("schema")}

ERROR:
{error}

PREVIOUS SQL:
{sql}

REQUIRED OUTPUT COLUMNS:
{required_columns}

STRICT REPAIR RULES:
- Stay within selected tables only
- Do NOT switch domain
- Fix only the failing part
- Do NOT add new tables
- Do NOT add new columns not present in provided schema
- Do NOT change user literals (dates, emp_id, ids)
- Preserve all required output columns
- If the query asks for login and logout, the repaired SQL must include login_time and logoff_time
- If the query asks for the date, include login_date
- Return complete corrected SQL, not partial SQL

OUTPUT:
SQL ONLY
""".strip()


# ------------------------------------------
# MAIN GENERATOR
# ------------------------------------------
def generate_sql(context: Dict[str, Any], llm=None) -> str:
    sql_llm = llm or get_llm("sql")

    prompt = build_sql_prompt(context)
    print("sql genneration:", prompt)
    response = sql_llm.invoke(prompt)

    sql = clean_sql(_extract_text_from_response(response))
    sql = _normalize_sql_server_syntax(sql)

    try:
        _basic_sql_check(sql)
        _enforce_domain_rules(sql, context)
        _enforce_schema_guards(sql, context)
        _enforce_required_columns(sql, context)
        print("[SQL] Generated:\n", sql)
        return sql

    except Exception as e:
        print("[SQL] First attempt failed:", str(e))

        repair_prompt = build_correction_prompt(context, sql, str(e))
        repair_response = sql_llm.invoke(repair_prompt)

        fixed_sql = clean_sql(_extract_text_from_response(repair_response))
        fixed_sql = _normalize_sql_server_syntax(fixed_sql)

        _basic_sql_check(fixed_sql)
        _enforce_domain_rules(fixed_sql, context)
        _enforce_schema_guards(fixed_sql, context)
        _enforce_required_columns(fixed_sql, context)

        print("[SQL] Corrected:\n", fixed_sql)
        return fixed_sql


def correct_sql(context: Dict[str, Any], previous_sql: str, error: str, llm=None) -> str:
    sql_llm = llm or get_llm("sql")

    prompt = build_correction_prompt(context, previous_sql, error)
    response = sql_llm.invoke(prompt)

    sql = clean_sql(_extract_text_from_response(response))
    sql = _normalize_sql_server_syntax(sql)

    _basic_sql_check(sql)
    _enforce_domain_rules(sql, context)
    _enforce_schema_guards(sql, context)
    _enforce_required_columns(sql, context)

    return sql