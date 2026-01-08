import pandas as pd
import numpy as np
import mlflow
from datetime import datetime

from src.utils import db_conn, read_sql, ensure_dir

HORIZONS = (1,7,14)

def load_latest_fs(conn, as_of_ds: str):
    df = read_sql(conn, """
        SELECT * FROM fs_daily_product_region
        WHERE ds = :ds
    """, params={"ds": as_of_ds})
    return df

def predict_all(db_path: str, as_of_ds: str, experiment="ecom_fs_forecast"):
    mlflow.set_experiment(experiment)
    ensure_dir("exports")

    with db_conn(db_path) as conn:
        X = load_latest_fs(conn, as_of_ds)

        if X.empty:
            raise ValueError(f"Não há linhas na FS para ds={as_of_ds}. Verifique o range de datas.")

        # mesmas features do treino
        feature_cols = [
            "n_orders","revenue","avg_price","avg_freight","n_sellers",
            "pay_total_avg","inst_avg","inst_max",
            "share_credit_card","share_boleto","share_voucher","share_debit_card",
            "dow","month","week_of_year",
            "qty_lag_1","qty_lag_7","qty_lag_14","qty_lag_28",
            "qty_roll_mean_7","qty_roll_mean_28",
            "cancel_qty","cancel_lag_1","cancel_lag_7","cancel_lag_14",
            "customer_state","product_id"
        ]

        Xf = X[feature_cols].copy()

        rows = []
        run_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        for h in HORIZONS:
            # modelos registrados pelo nome no treino
            demand_name = f"demand_product_region_h{h}"
            cancel_name = f"cancel_product_region_h{h}"

            demand_model = mlflow.pyfunc.load_model(f"models:/{demand_name}/latest")
            cancel_model = mlflow.pyfunc.load_model(f"models:/{cancel_name}/latest")

            pred_qty = demand_model.predict(Xf)
            pred_cancel = cancel_model.predict(Xf)

            # nossos modelos foram treinados com log1p(y), mas o wrapper já devolve o output do pipeline
            # (que no treino foi log space). Aqui precisamos replicar a inversão:
            pred_qty = np.clip(np.expm1(pred_qty), 0, None)
            pred_cancel = np.clip(np.expm1(pred_cancel), 0, None)

            ds_target = (pd.to_datetime(as_of_ds) + pd.Timedelta(days=h)).date().isoformat()

            out = pd.DataFrame({
                "run_date": run_date,
                "ds_base": as_of_ds,
                "ds_target": ds_target,
                "horizon": h,
                "product_id": X["product_id"].astype(str),
                "customer_state": X["customer_state"].astype(str),
                "pred_qty": pred_qty,
                "pred_cancel_qty": pred_cancel,
            })
            rows.append(out)

        pred = pd.concat(rows, ignore_index=True)

        # salva no SQLite
        conn.execute("DROP TABLE IF EXISTS pred_daily_product_region;")
        pred.to_sql("pred_daily_product_region", conn, if_exists="replace", index=False)

        # export para Power BI
        pred.to_csv("exports/pred_daily_product_region.csv", index=False)

    return pred

if __name__ == "__main__":
    df = predict_all("data/olist.db", as_of_ds="2018-08-26")
    print(df.head())
