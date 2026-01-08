
import os
import sqlite3
from contextlib import contextmanager

DB_PATH_DEFAULF = os.path.join("data", "olist.db")

@contextmanager
def db_conn(db_path: str = DB_PATH_DEFAULF):
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronus=NORMAL;")
        conn.execute("PRAGMA temp_store=MEMORY;")
        yield conn
        conn.commit()
    finally:
        conn.close()

def read_sql(conn, query: str, params=None):
    import pandas as pd
    return pd.read_sql_query(query, conn, params=params or {})

def exec_sql(conn, sql_text: str):
    try:
        conn.executescript(sql_text)
    except Exception as e:
        print(f"\n[ERRO SQL] Falhou ao executar script SQL. Erro: {e}")
        raise

def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)
