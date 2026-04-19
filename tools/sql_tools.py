# ==========================================
# SQL TOOLS (CUSTOM - STRUCTURED OUTPUT)
# ==========================================

from langchain_community.tools import BaseTool
from sqlalchemy import text
from sql.db import get_database


class QuerySQLDatabaseTool(BaseTool):
    name: str = "sql_db_query"
    description: str = "Execute SQL query and return structured result"

    def _run(self, query: str):
        try:
            db = get_database()
            engine = db._engine

            with engine.connect() as conn:
                result = conn.execute(text(query))

                rows = result.fetchall()
                columns = list(result.keys())

                return {
                    "rows": [tuple(row) for row in rows],
                    "columns": columns
                }

        except Exception as e:
            return {"error": str(e)}

    async def _arun(self, query: str):
        raise NotImplementedError()


# ------------------------------------------
# TOOL FACTORY
# ------------------------------------------
from tools.result_tool import result_processor


def get_sql_tools(db):
    return [
        QuerySQLDatabaseTool(),  # custom structured tool
        result_processor         # explanation tool
    ]