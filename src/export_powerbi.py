import os
from src.utils import db_conn, read_sql, ensure_dir

EXPORT_DIR = "exports"

TABLES = [
    "fs_daily_product_region",
    "pred_daily_product_region",
    "monitor_data_quality_weekly",
    "monitor_feature_drift_detail_weekly",
    "monitor_feature_drift_summary_weekly",
]

def export_all(db_path: str):
    ensure_dir(EXPORT_DIR)
    with db_conn(db_path) as conn:
        for t in TABLES:
            try:
                df = read_sql(conn, f"SELECT * FROM {t};")
            except Exception:
                continue
            out = os.path.join(EXPORT_DIR, f"{t}.csv")
            df.to_csv(out, index=False)
            print(f"[OK] Export {out} ({len(df):,} rows)")

if __name__ == "__main__":
    export_all("data/olist.db")
