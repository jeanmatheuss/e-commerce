import pandas as pd
import numpy as np
import mlflow
import os

from datetime import datetime
from mlflow.tracking import MlflowClient
from pathlib import Path

from src.utils import db_conn, read_sql, ensure_dir

HORIZONS = (1,7,14)
client = MlflowClient()
project_root = Path(__file__).resolve().parents[1]  # src/.. = raiz
mlruns_dir = project_root / "mlruns"
mlflow.set_tracking_uri(mlruns_dir.as_uri())

def load_latest_model(model_name: str, experiment_name: str = "ecom_fs_forecast", artifact_subpath: str = "model"):
    """
    1) Tenta carregar do Model Registry (models:/name/<versão>).
    2) Se Registry estiver vazio, carrega do último RUN que logou o artifact 'model'.
    """
    # --- 1) tenta registry (se existir)
    versions = client.search_model_versions(f"name='{model_name}'")
    if versions:
        latest = max(versions, key=lambda v: int(v.version))
        return mlflow.pyfunc.load_model(f"models:/{model_name}/{latest.version}")

    # --- 2) fallback via runs (sem registry)
    exp = client.get_experiment_by_name(experiment_name)
    if exp is None:
        raise RuntimeError(f"Experimento '{experiment_name}' não encontrado no tracking store atual.")

    runs = client.search_runs(
        [exp.experiment_id],
        filter_string=f"tags.model_name = '{model_name}'",
        order_by=["attributes.start_time DESC"],
        max_results=1,
    )
    if not runs:
        raise RuntimeError(
            f"Não encontrei RUN no experimento '{experiment_name}' com tag model_name='{model_name}'. "
            f"Garanta que no treino você setou mlflow.set_tag('model_name', model_name)."
        )

    run_id = runs[0].info.run_id
    return mlflow.pyfunc.load_model(f"runs:/{run_id}/{artifact_subpath}")

def load_latest_fs(conn, as_of_ds: str):
    df = read_sql(conn, """
        SELECT * FROM fs_daily_product_region
        WHERE ds = :ds
    """, params={"ds": as_of_ds})
    return df

def predict_all(db_path: str, as_of_ds: str, experiment="ecom_fs_forecast"):

    # força o mesmo tracking do treino (ajuste se necessário)
    mlruns_dir = os.path.abspath("mlruns")
    mlflow.set_tracking_uri(f"file:///{mlruns_dir}")

    print("[PRED] tracking_uri =", mlflow.get_tracking_uri())
    print("[PRED] mlruns_dir   =", mlruns_dir)

    client = MlflowClient()
    print("[PRED] registered_models =", [m.name for m in client.search_registered_models()])
        
    print("[PRED] MLFLOW_TRACKING_URI =", mlflow.get_tracking_uri())
    client = MlflowClient()
    print("[PRED] models =", [m.name for m in client.search_registered_models()])
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

            demand_model = load_latest_model(demand_name)
            cancel_model = load_latest_model(cancel_name)

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

#%%
client = MlflowClient()
print(client.search_model_versions("name='demand_product_region_h1'"))

# %%
