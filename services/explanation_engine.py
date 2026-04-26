# ==========================================
# Explanation Engine (Multi-table LLM Reasoning)
# ==========================================

def format_data_for_llm(db_result):
    """
    Convert DB result into structured readable format for LLM.
    """

    if not db_result or "rows" not in db_result:
        return "No data available"

    rows = db_result.get("rows", [])
    columns = db_result.get("columns", [])

    if not rows:
        return "No records found"

    formatted = ""

    for i, row in enumerate(rows):
        formatted += f"\nRecord {i+1}:\n"
        for col, val in zip(columns, row):
            formatted += f"- {col}: {val}\n"

    return formatted


# ------------------------------------------
# MAIN EXPLANATION FUNCTION
# ------------------------------------------
def generate_explanation(llm, query, db_result, context_plan=None):
    """
    LLM-driven explanation using multi-table data.
    NO hardcoded HR rules.
    """

    # --------------------------------------
    # STEP 1: Format DB result
    # --------------------------------------
    structured_data = format_data_for_llm(db_result)

    # --------------------------------------
    # STEP 2: Build intelligent prompt
    # --------------------------------------
    prompt = f"""
    You are an expert HR attendance analyst.

    User Query:
    {query}

    Available Data:
    {structured_data}

    Additional Context (Table Understanding):
    {context_plan}

    Your task:
    Explain WHY the attendance outcome occurred.

    Instructions:
    - Analyze the relationships between fields (login, logout, leave, shift, holiday)
    - Use only the data provided
    - Do NOT assume missing information
    - If data is insufficient, clearly say so
    - Think like an HR manager

    Focus on:
    - Missing punch
    - Leave status
    - Shift timing
    - Holiday/weekoff
    - Any inconsistencies

    Output:
    Clear, concise business explanation (3–6 lines)
    """

    # --------------------------------------
    # STEP 3: LLM reasoning
    # --------------------------------------
    try:
        response = llm.invoke(prompt)
        return response.content.strip()

    except Exception as e:
        print("[EXPLANATION ERROR]:", str(e))
        return "Unable to generate explanation."