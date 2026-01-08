from pathlib import Path
from src.utils import db_conn, exec_sql

def run_sql_file(db_path: str, sql_path: str):
    sql_text = Path(sql_path).read_text(encoding="utf-8")
    with db_conn(db_path) as conn:
        exec_sql(conn, sql_text)
    print(f"[OK] Executed {sql_path}")

def run_all(db_path: str):
    run_sql_file(db_path, "sql/00_schema_indexes.sql")
    run_sql_file(db_path, "sql/10_silver.sql")
    run_sql_file(db_path, "sql/20_gold.sql")
    run_sql_file(db_path, "sql/30_fs_daily.sql")

if __name__ == "__main__":
    run_all("data/olist.db")
