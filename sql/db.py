# ==========================================
# DB CONNECTION FILE (SECURE)
# ==========================================

import os
from urllib.parse import quote_plus
from dotenv import load_dotenv
from langchain_community.utilities import SQLDatabase

load_dotenv()


def get_database():
    """
    Returns LangChain SQLDatabase instance.
    """

    odbc_str = (
        f"DRIVER={{ODBC Driver 17 for SQL Server}};"
        f"SERVER={os.getenv('DB_SERVER')};"
        f"DATABASE={os.getenv('DB_NAME')};"
        f"UID={os.getenv('DB_USER')};"
        f"PWD={os.getenv('DB_PASSWORD')};"
        "TrustServerCertificate=yes;"
        "Connection Timeout=5;"
    )

    connect_str = quote_plus(odbc_str)
    db_uri = f"mssql+pyodbc:///?odbc_connect={connect_str}"

    return SQLDatabase.from_uri(
        db_uri,
        include_tables=[
            "login_mast",
            "emp_leave_setting",
            "shift_details",
            "emp_default_shift",
            "trnEmployeeWeeklyShift",
            "Leave_detail",
            "leave_dates",
            "holiday_master",
            "trnCandidateHolidayMapping",
            "cl_detail"
        ],
        sample_rows_in_table_info=1,
        view_support=True
    )