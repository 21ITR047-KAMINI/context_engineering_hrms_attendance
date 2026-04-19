# ==========================================
# LLM-driven Explanation Context Builder
# ==========================================

from llm.provider import get_llm
from rag.schema_loader import load_schema_docs

llm = get_llm()


def build_explanation_context(query: str):
    """
    Let LLM decide relevant tables and context dynamically.
    """

    schema_docs = load_schema_docs()

    prompt = f"""
You are an expert HR data analyst.

User Query:
{query}

Available Tables (with meaning):
{schema_docs}

Your task:
1. Identify relevant tables
2. Explain why each table is needed
3. Suggest what data to retrieve

Output format:

Tables:
- table_name: reason

Data Required:
- what fields to fetch
"""

    response = llm.invoke(prompt)

    return response.content.strip()