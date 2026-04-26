# ==========================================
# SQL Validator
# ==========================================

from __future__ import annotations

import re
from typing import Tuple, Any, Dict, List, Set

from llm.provider import get_llm


# ------------------------------------------
# CONSTANTS
# ------------------------------------------
FORBIDDEN_KEYWORDS = {
    "insert",
    "update",
    "delete",
    "drop",
    "truncate",
    "alter",
    "exec",
    "execute",
    "merge",
    "create",
    "grant",
    "revoke",
}


# ------------------------------------------
# CLEANING
# ------------------------------------------
def _clean_sql(sql: str) -> str:
    if not sql:
        return ""

    cleaned = sql.strip()

    code_block_match = re.search(
        r"```(?:sql)?\s*(.*?)```",
        cleaned,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if code_block_match:
        cleaned = code_block_match.group(1).strip()

    cleaned = re.sub(r"^\s*sql\s*", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = cleaned.rstrip(";").strip()

    return cleaned


# ------------------------------------------
# BASIC VALIDATION (HARD SAFETY)
# ------------------------------------------
def _only_single_statement(sql: str) -> bool:
    return ";" not in sql


def _balanced_single_quotes(sql: str) -> bool:
    i = 0
    in_quote = False

    while i < len(sql):
        ch = sql[i]

        if ch == "'":
            if i + 1 < len(sql) and sql[i + 1] == "'":
                i += 2
                continue
            in_quote = not in_quote

        i += 1

    return not in_quote


def _balanced_parentheses(sql: str) -> bool:
    depth = 0
    i = 0
    in_quote = False

    while i < len(sql):
        ch = sql[i]

        if ch == "'":
            if i + 1 < len(sql) and sql[i + 1] == "'":
                i += 2
                continue
            in_quote = not in_quote
            i += 1
            continue

        if not in_quote:
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth < 0:
                    return False

        i += 1

    return depth == 0 and not in_quote


def _starts_with_allowed_readonly_statement(sql: str) -> bool:
    sql_lower = sql.lower().lstrip()
    return sql_lower.startswith("select") or sql_lower.startswith("with")


def _contains_forbidden_keyword(sql: str) -> str | None:
    sql_lower = sql.lower()

    for keyword in FORBIDDEN_KEYWORDS:
        if re.search(rf"\b{re.escape(keyword)}\b", sql_lower):
            return keyword

    return None


def _basic_check(sql: str) -> Tuple[bool, str]:
    cleaned_sql = _clean_sql(sql)

    if not cleaned_sql:
        return False, "Empty SQL query"

    if len(cleaned_sql) > 12000:
        return False, "SQL query too long"

    if not _only_single_statement(cleaned_sql):
        return False, "Only a single SQL statement is allowed"

    if not _starts_with_allowed_readonly_statement(cleaned_sql):
        return False, "Only SELECT queries are allowed"

    forbidden_keyword = _contains_forbidden_keyword(cleaned_sql)
    if forbidden_keyword:
        return False, f"Forbidden keyword detected: {forbidden_keyword}"

    if not _balanced_single_quotes(cleaned_sql):
        return False, "Unbalanced single quotes in SQL"

    if not _balanced_parentheses(cleaned_sql):
        return False, "Unbalanced parentheses in SQL"

    return True, "Valid SQL"


# ------------------------------------------
# SCHEMA + LITERAL GUARDS (DETERMINISTIC)
# ------------------------------------------
def _extract_tables(sql: str) -> List[str]:
    pattern = re.compile(r"\b(?:from|join)\s+([a-zA-Z0-9_\.\[\]]+)", flags=re.IGNORECASE)
    found: List[str] = []

    for raw in pattern.findall(sql):
        table = raw.strip().strip("[]")
        if "." in table:
            table = table.split(".")[-1].strip("[]")
        if table:
            found.append(table)

    seen: Set[str] = set()
    ordered: List[str] = []
    for table in found:
        key = table.lower()
        if key not in seen:
            seen.add(key)
            ordered.append(table)

    return ordered


def _extract_alias_map(sql: str) -> Dict[str, str]:
    pattern = re.compile(
        r"\b(?:from|join)\s+([a-zA-Z0-9_\.\[\]]+)(?:\s+(?:as\s+)?([a-zA-Z_][a-zA-Z0-9_]*))?",
        flags=re.IGNORECASE,
    )
    alias_map: Dict[str, str] = {}

    for raw_table, alias in pattern.findall(sql):
        table = raw_table.strip().strip("[]")
        if "." in table:
            table = table.split(".")[-1].strip("[]")
        if alias:
            alias_map[alias.lower()] = table

    return alias_map


def _extract_column_references(sql: str) -> List[Tuple[str, str]]:
    stripped = re.sub(r"'(?:''|[^'])*'", "''", sql)
    pattern = re.compile(r"\b([a-zA-Z_][a-zA-Z0-9_]*)\.([a-zA-Z_][a-zA-Z0-9_]*)\b")
    return [(a.strip(), c.strip()) for a, c in pattern.findall(stripped)]


def _extract_date_literals(text: str) -> List[str]:
    return re.findall(r"\b\d{4}-\d{2}-\d{2}\b", text or "")


def _validate_against_schema(sql: str, context: Dict[str, Any]) -> Tuple[bool, str]:
    selected_tables = context.get("tables", []) or []
    schema = context.get("schema", {}) or {}

    if not selected_tables or not schema:
        return True, "Schema checks skipped (missing context schema/tables)"

    selected_map = {str(t).lower(): str(t) for t in selected_tables}

    schema_columns_map: Dict[str, Set[str]] = {}
    for table_name, table_meta in schema.items():
        if isinstance(table_meta, dict):
            cols = table_meta.get("columns", {})
            if isinstance(cols, dict):
                schema_columns_map[str(table_name).lower()] = {str(col).lower() for col in cols.keys()}

    sql_tables = _extract_tables(sql)
    if not sql_tables:
        return False, "No table found in SQL"

    for table in sql_tables:
        if table.lower() not in selected_map:
            return False, f"Table '{table}' is not in selected schema tables: {selected_tables}"

    if len(selected_tables) == 1 and len(sql_tables) > 1:
        return False, "Only one table was selected, but SQL uses joins/multiple tables"

    alias_map = _extract_alias_map(sql)
    for table_or_alias, column in _extract_column_references(sql):
        resolved_table = alias_map.get(table_or_alias.lower(), table_or_alias)
        table_key = resolved_table.lower()

        if table_key not in schema_columns_map:
            return False, f"Unknown table/alias reference '{table_or_alias}' for column '{column}'"

        if column.lower() not in schema_columns_map[table_key]:
            return False, f"Column '{column}' does not exist in table '{resolved_table}'"

    return True, "Schema validation passed"


def _validate_literal_consistency(sql: str, context: Dict[str, Any]) -> Tuple[bool, str]:
    query = context.get("query", "") or ""
    query_dates = set(_extract_date_literals(query))

    if not query_dates:
        return True, "No date literals in user query"

    sql_dates = set(_extract_date_literals(sql))
    if not sql_dates:
        return False, f"SQL is missing date literal(s) from user query: {sorted(query_dates)}"

    if not query_dates.issubset(sql_dates):
        return False, f"SQL changed date literal(s). Expected at least: {sorted(query_dates)}, got: {sorted(sql_dates)}"

    return True, "Literal consistency passed"


# ------------------------------------------
# LLM VALIDATION (SMART CHECK)
# ------------------------------------------
def _build_validation_prompt(sql: str, context: Dict[str, Any]) -> str:
    """
    Prompt stays inside validator (as per your architecture)
    """
    return f"""
You are an expert SQL validator.

Your job is to check whether the SQL query is:
- logically correct
- uses correct tables
- avoids unnecessary joins
- matches the user intent

USER QUERY:
{context.get("query", "")}

SELECTED TABLES:
{context.get("tables", [])}

SCHEMA:
{context.get("schema", {})}

SQL:
{sql}

RULES:
1. Do NOT rewrite SQL
2. Only validate
3. If correct → return VALID
4. If incorrect → return INVALID + reason

OUTPUT FORMAT:
VALID
or
INVALID: <reason>
""".strip()


def _llm_validate(sql: str, context: Dict[str, Any]) -> Tuple[bool, str]:
    try:
        llm = get_llm("sql")
        prompt = _build_validation_prompt(sql, context)

        response = llm.invoke(prompt)
        text = str(getattr(response, "content", response)).strip().lower()

        if text.startswith("valid"):
            return True, "LLM validation passed"

        return False, text

    except Exception as e:
        # fallback to deterministic validation only
        return True, f"LLM validation skipped: {str(e)}"


# ------------------------------------------
# MAIN VALIDATOR
# ------------------------------------------
def validate_sql(sql: str, context: Dict[str, Any] | None = None) -> Tuple[bool, str]:
    """
    Hybrid validation:
    1. HARD safety check (mandatory)
    2. Schema + literal guardrails (mandatory when context is present)
    3. LLM validation (optional)

    Returns:
        (is_valid, message)
    """

    cleaned_sql = _clean_sql(sql)
    is_valid, message = _basic_check(cleaned_sql)

    if not is_valid:
        return is_valid, message

    safe_context = context or {}

    schema_ok, schema_message = _validate_against_schema(cleaned_sql, safe_context)
    if not schema_ok:
        return False, schema_message

    literal_ok, literal_message = _validate_literal_consistency(cleaned_sql, safe_context)
    if not literal_ok:
        return False, literal_message

    if safe_context:
        llm_valid, llm_message = _llm_validate(cleaned_sql, safe_context)
        if not llm_valid:
            return False, llm_message

    return True, "Valid SQL"
