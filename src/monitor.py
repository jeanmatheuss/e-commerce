import pandas as pd
import numpy as np

from src.utils import db_conn, read_sql, ensure_dir

FEATURES_TO_MONITOR = [
    "n_orders","revenue","avg_price","avg_freight","n_sellers",
    "pay_total_avg","inst_avg","inst_max",
    "qty","cancel_qty",
    "qty_roll_mean_7","qty_roll_mean_28",
]

def compute_quality(df_fs: pd.DataFrame) -> pd.DataFrame:
    out = {
        "n_rows": len(df_fs),
    }
    for c in FEATURES_TO_MONITOR:
        if c in df_fs.columns:
            out[f"missing_pct_{c}"] = float(df_fs[c].isna().mean() * 100.0)
    return pd.DataFrame([out])

def compute_drift(train_df: pd.DataFrame, current_df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for c in FEATURES_TO_MONITOR:
        if c not in train_df.columns or c not in current_df.columns:
            continue

        t = pd.to_numeric(train_df[c], errors="coerce")
        u = pd.to_numeric(current_df[c], errors="coerce")

        t_mean, t_std = np.nanmean(t), np.nanstd(t) + 1e-9
        u_mean, u_std = np.nanmean(u), np.nanstd(u) + 1e-9

        z = (u_mean - t_mean) / t_std
        rows.append({
            "feature": c,
            "train_mean": float(t_mean),
            "train_std": float(t_std),
            "current_mean": float(u_mean),
            "current_std": float(u_std),
            "z_diff": float(z),
        })

    drift = pd.DataFrame(rows)
    if not drift.empty:
        drift["flag_z_gt_2"] = (drift["z_diff"].abs() > 2).astype(int)
        drift_score = drift["flag_z_gt_2"].mean() * 100.0
    else:
        drift_score = 0.0

    drift_summary = pd.DataFrame([{"drift_score_pct_features_z_gt_2": drift_score}])
    return drift, drift_summary

def monitor(db_path: str, as_of_ds: str, train_window_days: int = 180):
    ensure_dir("exports")
    with db_conn(db_path) as conn:
        fs = read_sql(conn, "SELECT * FROM fs_daily_product_region ORDER BY ds;")
        fs["ds"] = pd.to_datetime(fs["ds"], errors="coerce")
        fs = fs.dropna(subset=["ds"])

        as_of = pd.to_datetime(as_of_ds)
        train_start = as_of - pd.Timedelta(days=train_window_days)

        train_df = fs[(fs["ds"] >= train_start) & (fs["ds"] <= as_of)].copy()
        current_df = fs[fs["ds"] == as_of].copy()

        quality = compute_quality(current_df)
        drift_detail, drift_summary = compute_drift(train_df, current_df)

        # salvar
        quality.to_csv("exports/monitor_data_quality_weekly.csv", index=False)
        drift_detail.to_csv("exports/monitor_feature_drift_detail_weekly.csv", index=False)
        drift_summary.to_csv("exports/monitor_feature_drift_summary_weekly.csv", index=False)

        # também no SQLite
        conn.execute("DROP TABLE IF EXISTS monitor_data_quality_weekly;")
        quality.to_sql("monitor_data_quality_weekly", conn, if_exists="replace", index=False)

        conn.execute("DROP TABLE IF EXISTS monitor_feature_drift_detail_weekly;")
        drift_detail.to_sql("monitor_feature_drift_detail_weekly", conn, if_exists="replace", index=False)

        conn.execute("DROP TABLE IF EXISTS monitor_feature_drift_summary_weekly;")
        drift_summary.to_sql("monitor_feature_drift_summary_weekly", conn, if_exists="replace", index=False)

    return quality, drift_summary

if __name__ == "__main__":
    q, d = monitor("data/olist.db", as_of_ds="2018-08-26")
    print(q)
    print(d)
