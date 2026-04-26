# ==========================================
# DB SCHEMA EXTRACTION (RAG COMPATIBLE)
# ==========================================

from sql.db import get_database
from functools import lru_cache

@lru_cache(maxsize=1)
def get_db_schema():
    """
    Convert SQLDatabase → dict format for RAG
    """

    db = get_database()
    schema = {}

    try:
        tables = db.get_usable_table_names()

        for table in tables:
            try:
                table_info = db.get_table_info([table])

                columns = []

                for line in table_info.split("\n"):
                    line = line.strip()

                    # Skip unwanted lines
                    if (
                        not line
                        or line.startswith("CREATE")
                        or line.startswith(")")
                        or "(" in line
                    ):
                        continue

                    # Extract column name
                    col = line.split()[0].strip(",")
                    columns.append(col)

                schema[table] = columns

            except Exception as e:
                print(f"[TABLE ERROR]: {table} → {e}")

        return schema

    except Exception as e:
        print("[SCHEMA ERROR]:", e)
        return {}
    
   