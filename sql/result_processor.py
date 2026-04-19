# ==========================================
# Result Processor (Formatting + AI Explanation + HR Insights)
# ==========================================

from llm.provider import get_llm

llm = get_llm()


# ------------------------------------------
# TABLE FORMATTER
# ------------------------------------------
def format_table(rows, columns):
    if not rows:
        return "No data found."

    output = ""

    # Header
    output += " | ".join(columns) + "\n"
    output += "-" * 80 + "\n"

    # Rows
    for row in rows:
        output += " | ".join(str(col) for col in row) + "\n"

    return output


# ------------------------------------------
# RULE-BASED PATTERN DETECTION (HR LOGIC)
# ------------------------------------------
def detect_patterns(rows, columns):
    """
    Detect common attendance issues based on HR rules.
    """

    insights = []

    if not rows or not columns:
        return insights

    # Missing punch detection
    if "login_time" in columns:
        idx = columns.index("login_time")
        for row in rows:
            if row[idx] is None:
                insights.append("Missing login detected → may lead to leave marking")

    if "logoff_time" in columns:
        idx = columns.index("logoff_time")
        for row in rows:
            if row[idx] is None:
                insights.append("Missing logout detected → may lead to leave marking")

    return list(set(insights))  # remove duplicates


# ------------------------------------------
# AI EXPLANATION (LLM)
# ------------------------------------------
def generate_explanation(query, rows, columns):
    """
    Use LLM to dynamically explain result.
    """

    sample_rows = rows[:10]

    prompt = f"""
You are an HR analytics assistant.

User Query:
{query}

Database Result:
Columns: {columns}
Rows: {sample_rows}

Your task:
1. Provide a short summary
2. Highlight key insights
3. Explain in simple business language

Rules:
- Do NOT repeat raw data
- Do NOT hallucinate
- Be concise and clear
- Focus on meaning

Output Format:

Summary:
<short summary>

Insights:
<key insights>

Explanation:
<simple explanation>
"""

    try:
        response = llm.invoke(prompt)
        return response.content.strip()

    except Exception as e:
        print("[EXPLANATION ERROR]:", str(e))
        return "Unable to generate explanation."


# ------------------------------------------
# MAIN RESULT PROCESSOR
# ------------------------------------------
def process_result(db_result, query=None):

    try:
        # --------------------------------------
        # 🔥 STEP 0: HANDLE INVALID RESPONSE
        # --------------------------------------
        if not db_result:
            return {
                "explanation": "Data not found",
                "rows": [],
                "columns": []
            }

        # --------------------------------------
        # 🔥 STEP 1: HANDLE DB ERROR (CRITICAL FIX)
        # --------------------------------------
        if isinstance(db_result, dict) and "error" in db_result:

            print("[DB ERROR RAW]:", db_result["error"])  # keep for logs

            return {
                "explanation": "Data not found",
                "rows": [],
                "columns": []
            }

        # --------------------------------------
        # 🔥 STEP 2: HANDLE STRING ERROR RESPONSE
        # --------------------------------------
        if isinstance(db_result, str) and "error" in db_result.lower():

            print("[DB ERROR STRING]:", db_result)

            return {
                "explanation": "Data not found",
                "rows": [],
                "columns": []
            }

        # --------------------------------------
        # STEP 3: NORMAL DATA EXTRACTION
        # --------------------------------------
        rows = db_result.get("rows", [])
        columns = db_result.get("columns", [])

        # --------------------------------------
        # 🔥 STEP 4: EMPTY RESULT HANDLING
        # --------------------------------------
        if not rows:
            return {
                "explanation": "Data not found",
                "rows": [],
                "columns": columns
            }

        # --------------------------------------
        # STEP 5: PATTERN DETECTION
        # --------------------------------------
        patterns = detect_patterns(rows, columns)

        # --------------------------------------
        # STEP 6: AI EXPLANATION
        # --------------------------------------
        explanation = ""
        if query:
            explanation = generate_explanation(query, rows, columns)

        # --------------------------------------
        # STEP 7: ADD PATTERN INSIGHTS
        # --------------------------------------
        if patterns:
            pattern_text = "\n".join(f"- {p}" for p in patterns)
            explanation += f"\n\nDetected Issues:\n{pattern_text}"

        return {
            "explanation": explanation,
            "rows": rows,
            "columns": columns
        }

    except Exception as e:
        print("[RESULT PROCESSOR ERROR]:", str(e))

        return {
            "explanation": "Data not found",
            "rows": [],
            "columns": []
        }