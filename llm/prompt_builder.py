# ==========================================
# Prompt Builder
# ==========================================

from __future__ import annotations

from typing import Any, Dict, List, Optional


# ------------------------------------------
# HELPERS
# ------------------------------------------
def _safe_str(value: Any) -> str:
    if value is None:
        return "null"
    return str(value)


def _dedupe_keep_order(items: List[str]) -> List[str]:
    seen = set()
    output: List[str] = []

    for item in items:
        cleaned = str(item).strip()
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            output.append(cleaned)

    return output


def _extract_tables(context: Dict[str, Any]) -> List[str]:
    tables = context.get("tables", [])
    if isinstance(tables, list):
        return [str(table).strip() for table in tables if str(table).strip()]
    return []


def _extract_schema(context: Dict[str, Any]) -> Dict[str, Any]:
    schema = context.get("schema", {})
    return schema if isinstance(schema, dict) else {}


def _extract_rules(context: Dict[str, Any]) -> List[str]:
    rules = context.get("rules", [])
    if isinstance(rules, list):
        return [str(rule).strip() for rule in rules if str(rule).strip()]
    return []


def _extract_join_hints(context: Dict[str, Any]) -> List[str]:
    join_hints = context.get("join_hints", [])
    if isinstance(join_hints, list):
        return [str(hint).strip() for hint in join_hints if str(hint).strip()]
    return []


def _extract_business_focus(context: Dict[str, Any]) -> List[str]:
    business_focus = context.get("business_focus", [])
    if isinstance(business_focus, list):
        return [str(item).strip() for item in business_focus if str(item).strip()]
    return []


def _extract_query(context: Dict[str, Any]) -> str:
    return str(context.get("query", "")).strip()


def _extract_intent(context: Dict[str, Any]) -> str:
    return str(context.get("intent", "attendance")).strip()


def _extract_query_analysis(context: Dict[str, Any]) -> Dict[str, Any]:
    query_analysis = context.get("query_analysis", {})
    return query_analysis if isinstance(query_analysis, dict) else {}


def _format_schema_block(schema: Dict[str, Any]) -> str:
    """
    Convert structured schema metadata into a readable block for LLM prompts.
    """
    if not schema:
        return "No schema available."

    blocks: List[str] = []

    for table_name, meta in schema.items():
        if not isinstance(meta, dict):
            continue

        description = _safe_str(meta.get("description", ""))
        domain = _safe_str(meta.get("domain", ""))

        columns = meta.get("columns", {})
        if isinstance(columns, dict):
            column_lines = [
                f"  - {col}: {desc}"
                for col, desc in columns.items()
            ]
        else:
            column_lines = []

        primary_keys = meta.get("primary_keys", [])
        business_keys = meta.get("business_keys", [])
        used_for = meta.get("used_for", [])
        join_hints = meta.get("join_hints", [])

        block = [
            f"Table: {table_name}",
            f"Domain: {domain}",
            f"Description: {description}",
        ]

        if primary_keys:
            block.append("Primary Keys: " + ", ".join(str(x) for x in primary_keys))
        if business_keys:
            block.append("Business Keys: " + ", ".join(str(x) for x in business_keys))
        if used_for:
            block.append("Used For: " + ", ".join(str(x) for x in used_for))
        if join_hints:
            block.append("Table Join Hints:")
            block.extend([f"  - {hint}" for hint in join_hints])

        if column_lines:
            block.append("Columns:")
            block.extend(column_lines)

        blocks.append("\n".join(block))

    return "\n\n".join(blocks) if blocks else "No schema available."


def _format_rules_block(rules: List[str], max_rules: int = 25) -> str:
    if not rules:
        return "No business rules available."

    trimmed = _dedupe_keep_order(rules)[:max_rules]
    return "\n".join(f"- {rule}" for rule in trimmed)


def _format_join_hints_block(join_hints: List[str], max_hints: int = 20) -> str:
    if not join_hints:
        return "No join hints available."

    trimmed = _dedupe_keep_order(join_hints)[:max_hints]
    return "\n".join(f"- {hint}" for hint in trimmed)


def _format_business_focus_block(business_focus: List[str]) -> str:
    if not business_focus:
        return "No business focus available."
    return "\n".join(f"- {item}" for item in _dedupe_keep_order(business_focus))


def _format_query_analysis_block(query_analysis: Dict[str, Any]) -> str:
    if not query_analysis:
        return "No query analysis available."

    lines = []
    for key, value in query_analysis.items():
        lines.append(f"- {key}: {_safe_str(value)}")
    return "\n".join(lines)


def _format_result_block(result: Dict[str, Any], max_rows: int = 5) -> str:
    """
    Format DB result for explanation prompts.
    Expects normalized result:
    {
        "rows": [...],
        "columns": [...],
        "error": None,
        "row_count": int
    }
    """
    if not isinstance(result, dict):
        return "No result available."

    error = result.get("error")
    if error:
        return f"Result Error: {_safe_str(error)}"

    rows = result.get("rows", [])
    columns = result.get("columns", [])

    if not rows:
        return "No rows returned."

    lines: List[str] = []
    lines.append(f"Row Count: {_safe_str(result.get('row_count', len(rows)))}")

    preview_rows = rows[:max_rows]

    # rows already as dict
    if preview_rows and isinstance(preview_rows[0], dict):
        for idx, row in enumerate(preview_rows, start=1):
            lines.append(f"Row {idx}:")
            for key, value in row.items():
                lines.append(f"  - {key}: {_safe_str(value)}")
        if len(rows) > max_rows:
            lines.append(f"... {len(rows) - max_rows} more row(s) omitted.")
        return "\n".join(lines)

    # rows as tuples/lists with columns
    if preview_rows and columns and isinstance(preview_rows[0], (list, tuple)):
        for idx, row in enumerate(preview_rows, start=1):
            lines.append(f"Row {idx}:")
            for col_idx, col_name in enumerate(columns):
                value = row[col_idx] if col_idx < len(row) else None
                lines.append(f"  - {col_name}: {_safe_str(value)}")
        if len(rows) > max_rows:
            lines.append(f"... {len(rows) - max_rows} more row(s) omitted.")
        return "\n".join(lines)

    # fallback
    for idx, row in enumerate(preview_rows, start=1):
        lines.append(f"Row {idx}: {_safe_str(row)}")
    if len(rows) > max_rows:
        lines.append(f"... {len(rows) - max_rows} more row(s) omitted.")

    return "\n".join(lines)


# ------------------------------------------
# SQL GENERATION PROMPT
# ------------------------------------------
def build_sql_prompt(context: Dict[str, Any]) -> str:
    """
    Build SQL generation prompt from structured RAG context.
    """
    query = _extract_query(context)
    intent = _extract_intent(context)
    tables = _extract_tables(context)
    schema = _extract_schema(context)
    rules = _extract_rules(context)
    join_hints = _extract_join_hints(context)
    business_focus = _extract_business_focus(context)
    query_analysis = _extract_query_analysis(context)

    schema_block = _format_schema_block(schema)
    rules_block = _format_rules_block(rules)
    join_block = _format_join_hints_block(join_hints)
    focus_block = _format_business_focus_block(business_focus)
    analysis_block = _format_query_analysis_block(query_analysis)

    table_list = ", ".join(tables) if tables else "No selected tables"

    prompt = f"""
You are an expert HRMS SQL generator.

Your task is to generate a single safe SQL query that answers the user question using ONLY the provided schema and business context.

USER QUERY:
{query}

INTENT:
{intent}

SELECTED TABLES:
{table_list}

QUERY ANALYSIS:
{analysis_block}

BUSINESS FOCUS:
{focus_block}

SCHEMA METADATA:
{schema_block}

BUSINESS RULES:
{rules_block}

JOIN HINTS:
{join_block}

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
Return only the SQL query.
""".strip()

    return prompt


# ------------------------------------------
# SQL CORRECTION PROMPT
# ------------------------------------------
def build_sql_correction_prompt(
    context: Dict[str, Any],
    previous_sql: str,
    validation_error: str = "",
    db_error: str = "",
) -> str:
    """
    Build SQL correction prompt using previous SQL + error feedback.
    """
    query = _extract_query(context)
    intent = _extract_intent(context)
    tables = _extract_tables(context)
    schema = _extract_schema(context)
    rules = _extract_rules(context)
    join_hints = _extract_join_hints(context)
    business_focus = _extract_business_focus(context)
    query_analysis = _extract_query_analysis(context)

    schema_block = _format_schema_block(schema)
    rules_block = _format_rules_block(rules)
    join_block = _format_join_hints_block(join_hints)
    focus_block = _format_business_focus_block(business_focus)
    analysis_block = _format_query_analysis_block(query_analysis)

    table_list = ", ".join(tables) if tables else "No selected tables"
    error_block = f"""
VALIDATION ERROR:
{validation_error or "None"}

DATABASE ERROR:
{db_error or "None"}
""".strip()

    prompt = f"""
You are an expert HRMS SQL correction assistant.

Your task is to fix the previous SQL query using the same user intent, schema, and business rules.

USER QUERY:
{query}

INTENT:
{intent}

SELECTED TABLES:
{table_list}

QUERY ANALYSIS:
{analysis_block}

BUSINESS FOCUS:
{focus_block}

SCHEMA METADATA:
{schema_block}

BUSINESS RULES:
{rules_block}

JOIN HINTS:
{join_block}

PREVIOUS SQL:
{previous_sql}

ERROR FEEDBACK:
{error_block}

INSTRUCTIONS:
1. Fix the SQL while preserving the user's original meaning.
2. Use ONLY the selected tables and columns provided above.
3. Do not invent tables or columns.
4. Correct join conditions if needed.
5. Correct date filters, aliases, or selected columns if needed.
6. If validation failed, fix syntax/safety issues.
7. If DB execution failed, fix semantic or structural SQL issues.
8. Return exactly one corrected SQL statement.

SAFETY RULES:
- Output SQL only.
- No markdown.
- No code fences.
- No explanation.
- No comments.
- No destructive SQL.
- Prefer SELECT only.
- If needed, a safe WITH clause followed by SELECT is allowed.

OUTPUT:
Return only the corrected SQL query.
""".strip()

    return prompt


# ------------------------------------------
# EXPLANATION PROMPT
# ------------------------------------------
def build_explanation_prompt(
    query: str,
    result: Dict[str, Any],
    context: Dict[str, Any],
) -> str:
    """
    Build explanation prompt from query + DB result + RAG context.
    This is optional because the explanation agent can call it, but
    keeping it here centralizes prompt construction.
    """
    clean_query = str(query or "").strip()

    tables = _extract_tables(context)
    rules = _extract_rules(context)
    join_hints = _extract_join_hints(context)
    business_focus = _extract_business_focus(context)
    query_analysis = _extract_query_analysis(context)

    table_list = ", ".join(tables) if tables else "No selected tables"
    rules_block = _format_rules_block(rules)
    join_block = _format_join_hints_block(join_hints)
    focus_block = _format_business_focus_block(business_focus)
    analysis_block = _format_query_analysis_block(query_analysis)
    result_block = _format_result_block(result)

    prompt = f"""
You are an expert HRMS reasoning analyst.

Your task is to answer the user's question using ONLY the provided database evidence and business rules.

USER QUERY:
{clean_query}

SELECTED TABLES:
{table_list}

QUERY ANALYSIS:
{analysis_block}

BUSINESS FOCUS:
{focus_block}

BUSINESS RULES:
{rules_block}

JOIN HINTS:
{join_block}

DATABASE RESULT:
{result_block}

INSTRUCTIONS:
1. Answer the user's actual question directly.
2. Use returned evidence first, then apply business rules carefully.
3. Do not invent facts not present in the result or rules.
4. If evidence is incomplete, say so clearly.
5. If evidence conflicts, mention the conflict.
6. For why-questions, explain the most likely supported reason.
7. Keep the response concise but meaningful.

OUTPUT STYLE:
- Human-readable
- 2 to 6 lines
- No SQL
- No JSON
- No markdown code blocks
""".strip()

    return prompt