# ==========================================
# SQL Validator (LLM-ready, agent-compatible)
# ==========================================

import re


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


def _clean_sql(sql: str) -> str:
    """
    Clean model-generated SQL.
    Removes markdown fences and trailing semicolon.
    """
    if not sql:
        return ""

    sql = sql.strip()

    # Remove markdown fences like ```sql ... ```
    sql = re.sub(r"^```sql\s*", "", sql, flags=re.IGNORECASE)
    sql = re.sub(r"^```\s*", "", sql)
    sql = re.sub(r"\s*```$", "", sql)

    # Remove trailing semicolon
    sql = sql.rstrip(";").strip()

    return sql


def _basic_check(sql: str):
    """
    Minimal safety validation.
    Keep it generic and not overly restrictive.
    """
    cleaned_sql = _clean_sql(sql)

    if not cleaned_sql:
        return False, "Empty SQL query"

    sql_lower = cleaned_sql.lower()

    # Only allow SELECT
    if not sql_lower.startswith("select"):
        return False, "Only SELECT queries are allowed"

    # Block destructive keywords
    for keyword in FORBIDDEN_KEYWORDS:
        if re.search(rf"\b{re.escape(keyword)}\b", sql_lower):
            return False, f"Forbidden keyword detected: {keyword}"

    # Basic quote balance check
    if cleaned_sql.count("'") % 2 != 0:
        return False, "Unbalanced single quotes in SQL"

    # Very long SQL guard
    if len(cleaned_sql) > 5000:
        return False, "SQL query too long"

    return True, "Valid SQL"


def validate_sql(sql: str):
    """
    Main validator used by agents.

    IMPORTANT:
    Must return exactly 2 values because current agents use:
        is_valid, message = validate_sql(sql)
    """
    return _basic_check(sql)