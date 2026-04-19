# ==========================================
# SQL Generator (Schema-Aware)
# ==========================================

from llm.provider import get_llm
from llm.prompt_builder import build_prompt
from rag.schema_selector import schema_selector

llm = get_llm()


# ------------------------------------------
# CLEAN SQL OUTPUT
# ------------------------------------------
def clean_sql(response_text: str) -> str:
    sql = response_text.strip()

    if "```" in sql:
        parts = sql.split("```")
        sql = parts[1] if len(parts) > 1 else sql

    sql = sql.replace("sql", "").strip()

    return sql


# ------------------------------------------
# BUILD SCHEMA CONTEXT
# ------------------------------------------
def build_schema_context(selected_schema: dict) -> str:
    """
    Convert selected schema into prompt-friendly text
    """

    context = "DATABASE SCHEMA:\n"

    for table, columns in selected_schema.items():
        context += f"\nTable: {table}\nColumns: {', '.join(columns)}\n"

    return context

# ==========================================
# Relationship Mapper (Table Join Logic)
# ==========================================

def get_table_relationships():
    """
    Defines relationships between tables.
    """

    return {
        "login_mast": {
            "emp_leave_setting": "login_mast.emp_id = emp_leave_setting.emp_id AND login_mast.login_date = emp_leave_setting.leave_date",
            "shift_details": "login_mast.shift_code = shift_details.shift_code",
            "cl_detail": "login_mast.emp_id = cl_detail.emp_id"
        },
        "emp_leave_setting": {
            "leave_dates": "emp_leave_setting.leave_id = leave_dates.leave_id"
        },
        "holiday_master": {
            "login_mast": "holiday_master.holi_date = login_mast.login_date"
        }
    }


# ------------------------------------------
# MAIN SQL GENERATOR
# ------------------------------------------


def build_join_context(selected_tables):
    """
    Build JOIN relationships for selected tables.
    """

    relationships = get_table_relationships()
    join_context = "TABLE RELATIONSHIPS:\n"

    for table in selected_tables:
        if table in relationships:
            for related_table, condition in relationships[table].items():
                if related_table in selected_tables:
                    join_context += f"{table} JOIN {related_table} ON {condition}\n"

    return join_context


def generate_sql(query: str, context: str = "") -> str:

    # STEP 1: Select schema
    selected_schema = schema_selector(query)

    print("[SCHEMA SELECTED]:", selected_schema.keys())

    # STEP 2: Build schema context
    schema_context = build_schema_context(selected_schema)

    # STEP 3: Build JOIN context
    join_context = build_join_context(selected_schema.keys())

    # Combine all context
    full_context = f"""
{schema_context}

{join_context}

ADDITIONAL CONTEXT:
{context}
"""

    # STEP 4: Build prompt
    prompt = build_prompt(query, full_context)

    # STEP 5: LLM call
    response = llm.invoke(prompt)
    sql = clean_sql(response.content)

    # STEP 6: Validation (existing)
    sql_lower = sql.lower()

    if "count(" in sql_lower and "group by" not in sql_lower:
        raise ValueError("Invalid SQL: COUNT without GROUP BY")

    if "login_date is null" in sql_lower:
        raise ValueError("Invalid logic: login_date cannot be NULL")

    if not sql_lower.startswith("select"):
        raise ValueError("Only SELECT queries allowed")

    print("[JOIN CONTEXT]:\n", join_context)
    print("[SQL_GENERATOR] Generated SQL:\n", sql)

    return sql