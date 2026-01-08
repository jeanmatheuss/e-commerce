#%%
import os
import pandas as pd
from src.utils import db_conn

RAW_DIR = os.path.join("data", "raw")

FILES = {
    "stg_orders": "olist_orders_dataset.csv",
    "stg_order_items": "olist_order_items_dataset.csv",
    "stg_products": "olist_products_dataset.csv",
    "stg_customers": "olist_customers_dataset.csv",
    "stg_sellers": "olist_sellers_dataset.csv",
    "stg_geolocation": "olist_geolocation_dataset.csv",
    "stg_payments": "olist_order_payments_dataset.csv",
    "stg_reviews": "olist_order_reviews_dataset.csv",
}

DATE_COLS = {
    "stg_orders": [
        "order_purchase_timestamp",
        "order_approved_at",
        "order_delivered_carrier_date",
        "order_delivered_customer_date",
        "order_estimated_delivery_date",
    ],
}

def _standardize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = [c.strip().lower() for c in df.columns]
    return df

def _parse_dates(table: str, df: pd.DataFrame) -> pd.DataFrame:
    cols = DATE_COLS.get(table, [])
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_datetime(df[c], errors='coerce')
            df[c] = df[c].dt.strftime("%Y-%m-%d %H:%M:%S")

    return df

def load_all (db_path: str, rebuild: bool = True):
    with db_conn(db_path) as conn:
        if rebuild:
            # DROP staging se existirem
            for t in FILES.keys():
                conn.execute(f"DROP TABLE IF EXISTS {t};")

        for table,fname in FILES.items():
            path = os.path.join(RAW_DIR, fname)
            if not os.path.exists(path):
                raise FileNotFoundError(f"Arquivo não encontrado: {path}")

            df= pd.read_csv(path)
            df = _standardize_columns(df)
            df = _parse_dates(table, df)

            df.to_sql(table, conn, if_exists="replace", index=False)
            print(f"[OK] Loaded {table} ({len(df):,} rows)")

    print("[OK] Staging carregado no SQLite")


if __name__ == "__main__":
    load_all(db_path=os.path.join("data", "olist.db"), rebuild=True)
# %%
