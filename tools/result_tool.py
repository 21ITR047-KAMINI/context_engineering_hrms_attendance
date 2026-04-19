from langchain.tools import tool
from llm.provider import get_llm

llm = get_llm()


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

        # Table formatting
        header = " | ".join(columns)
        separator = "-" * len(header)

        lines = [header, separator]

        for row in rows:
            lines.append(" | ".join(str(col) for col in row))

        table_output = "\n".join(lines)

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

        response = llm.invoke(prompt)
        explanation = response.content.strip()

        return f"""
{explanation}

📋 Data:
{table_output}
"""

    except Exception as e:
        return f"Result processing error: {str(e)}"