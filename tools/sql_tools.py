# ==========================================
# SQL Tools
# ==========================================

from __future__ import annotations

from typing import Any, Dict, List, Optional

from langchain_community.tools import BaseTool
from sqlalchemy import text

from sql.db import get_database


# ------------------------------------------
# NORMALIZATION HELPERS
# ------------------------------------------
def _normalize_result(
    rows: Optional[List[Any]] = None,
    columns: Optional[List[str]] = None,
    error: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Normalize SQL execution output into a stable structure.
    """
    safe_rows = rows if isinstance(rows, list) else []
    safe_columns = columns if isinstance(columns, list) else []

    return {
        "rows": safe_rows,
        "columns": safe_columns,
        "error": error,
        "row_count": len(safe_rows),
    }


def _rows_to_serializable(rows: List[Any]) -> List[Any]:
    """
    Convert SQLAlchemy rows into JSON-friendly Python structures.
    Prefer tuples for predictable positional row handling.
    """
    output: List[Any] = []

    for row in rows:
        try:
            output.append(tuple(row))
        except Exception:
            try:
                output.append(dict(row))
            except Exception:
                output.append(str(row))

    return output


# ------------------------------------------
# DIRECT SQL EXECUTION
# ------------------------------------------
def execute_sql(query: str) -> Dict[str, Any]:
    """
    Execute SQL query and return normalized structured output.

    Expected return format:
    {
        "rows": [...],
        "columns": [...],
        "error": None | str,
        "row_count": int
    }
    """
    if not isinstance(query, str) or not query.strip():
        return _normalize_result(error="Empty SQL query")

    try:
        db = get_database()
        engine = db._engine

        with engine.connect() as conn:
            result = conn.execute(text(query))

            try:
                fetched_rows = result.fetchall()
                columns = list(result.keys())
            except Exception:
                # Some SQL statements may not produce fetchable rows,
                # but in this project we expect SELECT-style queries.
                fetched_rows = []
                columns = []

        serializable_rows = _rows_to_serializable(fetched_rows)

        return _normalize_result(
            rows=serializable_rows,
            columns=columns,
            error=None,
        )

    except Exception as exc:
        return _normalize_result(
            rows=[],
            columns=[],
            error=str(exc),
        )


# ------------------------------------------
# LANGCHAIN TOOL WRAPPER
# ------------------------------------------
class QuerySQLDatabaseTool(BaseTool):
    name: str = "sql_db_query"
    description: str = "Execute SQL query and return structured result"

    def _run(self, query: str) -> Dict[str, Any]:
        return execute_sql(query)

    async def _arun(self, query: str) -> Dict[str, Any]:
        raise NotImplementedError("Async SQL execution is not implemented.")


# ------------------------------------------
# TOOL FACTORY
# ------------------------------------------
def get_sql_tools(db: Any = None) -> List[BaseTool]:
    """
    Backward-compatible tool factory.

    The current graph-driven architecture mainly uses execute_sql(query)
    directly, but this factory remains for compatibility with any legacy code.
    """
    return [
        QuerySQLDatabaseTool(),
    ]

def fetch_table_sample(table_name: str, limit: int = 2) -> dict:
    """
    Fetch a small sample from a table for LLM grounding.
    Used only for prompt context, not final answer.
    """
    try:
        db = get_database()
        engine = db._engine

        safe_table = table_name.replace("[", "").replace("]", "").strip()

        query = f"SELECT TOP ({limit}) * FROM {safe_table}"

        with engine.connect() as conn:
            result = conn.execute(text(query))
            rows = result.fetchall()
            columns = list(result.keys())

            return {
                "table": safe_table,
                "columns": columns,
                "rows": [dict(zip(columns, row)) for row in rows],
                "error": None,
            }

    except Exception as e:
        return {
            "table": table_name,
            "columns": [],
            "rows": [],
            "error": str(e),
        }