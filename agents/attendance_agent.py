# ==========================================
# Attendance Agent (Prompt-driven - FINAL)
# ==========================================

from sql.sql_generator import generate_sql
from sql.sql_validator import validate_sql
from sql.result_processor import process_result
import ast


def create_attendance_agent(llm, tools):

    # ------------------------------------------
    # GET REQUIRED TOOLS
    # ------------------------------------------
    sql_tool = next((t for t in tools if t.name == "sql_db_query"), None)

    if not sql_tool:
        raise ValueError("SQL Query Tool not found")

    # ------------------------------------------
    # MAIN AGENT NODE
    # ------------------------------------------
    def agent_node(state):
        try:
            query = state["query"]

            print(f"\n[ATTENDANCE AGENT] Query: {query}")

            # ----------------------------------
            # STEP 1: BUILD PROMPT (CORE FIX)
            # ----------------------------------
            prompt = f"""
You are an expert HR attendance SQL assistant.

User Query:
{query}

Available Table:
login_mast(
    emp_id,
    login_date,
    login_time,
    logoff_time,
    shift_code
)

COLUMN MEANING:
- login_time → actual login timestamp
- logoff_time → actual logout timestamp
- login_date → reference date (use only for filtering)

BUSINESS RULES:
- "working hours" = difference between login_time and logoff_time
- DO NOT use shift_details unless explicitly asked
- Always use login_time/logoff_time for time calculations
- Use CAST(login_time AS DATE) when needed

STRICT RULES:
- Generate ONLY SQL query
- DO NOT explain
- DO NOT add comments
- DO NOT use unknown tables
- Use only given columns

OUTPUT:
SQL query only
"""

            # ----------------------------------
            # STEP 2: Generate SQL
            # ----------------------------------
            sql = generate_sql(prompt)
            print(f"[SQL]: {sql}")

            # ----------------------------------
            # STEP 3: Validate SQL
            # ----------------------------------
            is_valid, message = validate_sql(sql)

            if not is_valid:
                return {
                    "response": f"Invalid SQL: {message}"
                }

            # ----------------------------------
            # STEP 4: Execute SQL
            # ----------------------------------
            result = sql_tool.invoke({"query": sql})

            print(f"[DB RESULT RAW]: {result}")
            print(f"[DB RESULT TYPE]: {type(result)}")

            # ----------------------------------
            # STEP 5: Normalize DB Result
            # ----------------------------------
            if isinstance(result, str):
                try:
                    parsed = ast.literal_eval(result)

                    if isinstance(parsed, list):
                        result = {
                            "rows": parsed,
                            "columns": []
                        }

                except Exception:
                    return {
                        "response": "Failed to parse DB result"
                    }

            if not isinstance(result, dict):
                return {
                    "response": "Invalid DB result format"
                }

            # ----------------------------------
            # STEP 6: Process Result
            # ----------------------------------
            final_output = process_result(result, query)

            # ----------------------------------
            # STEP 7: Final Response
            # ----------------------------------
            return {
                "response": final_output
            }

        except Exception as e:
            print("AGENT ERROR:", str(e))
            return {
                "response": "Data not found"
            }

    return agent_node