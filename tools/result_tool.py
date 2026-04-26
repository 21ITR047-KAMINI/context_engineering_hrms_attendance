from langchain.tools import tool
from llm.provider import get_llm


def _get_result_llm():
    return get_llm()


def format_table_view(rows: list, columns: list) -> str:
    """
    Build a fixed-width text table for fallback/plain-text display.
    """
    if not rows or not columns:
        return "Data not found"

    normalized_rows = [list(row) if isinstance(row, (list, tuple)) else [row] for row in rows]
    col_count = len(columns)

    widths = [len(str(col)) for col in columns]
    for row in normalized_rows:
        for i in range(col_count):
            value = row[i] if i < len(row) else ""
            widths[i] = max(widths[i], len(str(value)))

    header = " | ".join(str(columns[i]).ljust(widths[i]) for i in range(col_count))
    separator = "-+-".join("-" * widths[i] for i in range(col_count))
    lines = [header, separator]

    for row in normalized_rows:
        line = " | ".join(
            str(row[i] if i < len(row) else "").ljust(widths[i])
            for i in range(col_count)
        )
        lines.append(line)

    return "\n".join(lines)


@tool
def result_processor(query: str, db_result: dict) -> str:
    """
    Process database result into summary, insights, and explanation.

    Args:
        query: User query
        db_result: Dictionary containing rows and columns from database

    Returns:
        Formatted response with explanation and table
    """

    try:
        rows = db_result.get("rows", [])
        columns = db_result.get("columns", [])

        if not rows:
            return "No matching records found."

        table_output = format_table_view(rows, columns)

        # LLM explanation
        sample_rows = rows[:10]

        prompt = f"""
        You are an HR analytics assistant.

        User Query:
        {query}

        Database Result:
        Columns: {columns}
        Rows: {sample_rows}

        STRICT RULES:
        - Use only given data
        - Do not assume missing info
        - Avoid overconfidence

        Provide:
        Summary:
        Insights:
        Explanation:
        """

        llm = _get_result_llm()
        response = llm.invoke(prompt)
        explanation = response.content.strip()

        return f"""
{explanation}

📋 Data:
{table_output}
"""

    except Exception as e:
        return f"Result processing error: {str(e)}"
