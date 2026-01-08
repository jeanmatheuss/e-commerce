import os
import numpy as np
import pandas as pd
import mlflow
import mlflow.sklearn
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from sklearn.impute import SimpleImputer
from sklearn.ensemble import HistGradientBoostingRegressor

from src.utils import db_conn, read_sql, ensure_dir

FEATURE_COLS_NUM = [
    "n_orders","revenue","avg_price","avg_freight","n_sellers",
    "pay_total_avg","inst_avg","inst_max",
    "share_credit_card","share_boleto","share_voucher","share_debit_card",
    "dow","month","week_of_year",
    "qty_lag_1","qty_lag_7","qty_lag_14","qty_lag_28",
    "qty_roll_mean_7","qty_roll_mean_28",
    "cancel_qty","cancel_lag_1","cancel_lag_7","cancel_lag_14",
]
FEATURE_COLS_CAT = ["customer_state"]  # região
# product_id é alta cardinalidade; para demo mantemos como categórica
FEATURE_COLS_CAT2 = ["product_id"]

def make_training_frame(conn) -> pd.DataFrame:
    df = read_sql(conn, """
        SELECT * FROM fs_daily_product_region
        WHERE ds IS NOT NULL AND product_id IS NOT NULL AND customer_state IS NOT NULL
        ORDER BY ds ASC
    """)
    df["ds"] = pd.to_datetime(df["ds"], errors="coerce")
    df = df.dropna(subset=["ds"])
    return df

def add_targets(df: pd.DataFrame, horizons=(1,7,14)) -> pd.DataFrame:
    # targets por grupo (produto×estado) usando shift negativo (futuro)
    df = df.sort_values(["product_id","customer_state","ds"])
    for h in horizons:
        df[f"y_qty_h{h}"] = df.groupby(["product_id","customer_state"])["qty"].shift(-h)
        df[f"y_cancel_h{h}"] = df.groupby(["product_id","customer_state"])["cancel_qty"].shift(-h)
    return df

def build_pipeline():
    numeric = Pipeline(steps=[
        ("imputer", SimpleImputer(strategy="median")),
    ])
    categorical = Pipeline(steps=[
        ("imputer", SimpleImputer(strategy="most_frequent")),
        ("ohe", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
    ])

    pre = ColumnTransformer(
        transformers=[
            ("num", numeric, FEATURE_COLS_NUM),
            ("cat_state", categorical, FEATURE_COLS_CAT),
            ("cat_prod", categorical, FEATURE_COLS_CAT2),
        ],
        remainder="drop",
        sparse_threshold=0.3
    )

    model = HistGradientBoostingRegressor(
        max_depth=6,
        learning_rate=0.08,
        max_iter=400,
        random_state=42
    )

    return Pipeline(steps=[("pre", pre), ("model", model)])

def eval_metrics(y_true, y_pred):
    mae = mean_absolute_error(y_true, y_pred)
    rmse = mean_squared_error(y_true, y_pred)
    # MAPE com cuidado para zero
    denom = np.maximum(np.abs(y_true), 1e-6)
    mape = np.mean(np.abs((y_true - y_pred) / denom)) * 100.0
    return {"mae": mae, "rmse": rmse, "mape": mape}

def time_split(df: pd.DataFrame, train_end: str, val_weeks: int = 8):
    # split por tempo (semanal): tudo <= train_end é treino; as últimas val_weeks semanas são validação
    train_end_dt = pd.to_datetime(train_end)
    df = df[df["ds"] <= train_end_dt].copy()
    if df.empty:
        raise ValueError("Sem dados após aplicar train_end.")

    max_ds = df["ds"].max()
    val_start = max_ds - pd.Timedelta(weeks=val_weeks)
    train_df = df[df["ds"] < val_start].copy()
    val_df = df[df["ds"] >= val_start].copy()

    if train_df.empty or val_df.empty:
        raise ValueError("Split inválido: ajuste train_end ou val_weeks.")
    return train_df, val_df

def train_all(db_path: str, train_end: str, horizons=(1,7,14), experiment="ecom_fs_forecast"):
    ensure_dir("mlruns")
    mlflow.set_experiment(experiment)

    with db_conn(db_path) as conn:
        base = make_training_frame(conn)
    base = add_targets(base, horizons=horizons)

    # Remover linhas sem target para cada horizonte no momento do treino
    feature_cols = FEATURE_COLS_NUM + FEATURE_COLS_CAT + FEATURE_COLS_CAT2

    results = []

    for h in horizons:
        for target_name in [f"y_qty_h{h}", f"y_cancel_h{h}"]:
            df = base.dropna(subset=[target_name]).copy()

            # split temporal
            train_df, val_df = time_split(df, train_end=train_end, val_weeks=8)

            X_train = train_df[feature_cols]
            y_train = np.log1p(train_df[target_name].astype(float).values)

            X_val = val_df[feature_cols]
            y_val_true = val_df[target_name].astype(float).values

            pipe = build_pipeline()

            run_name = f"{target_name}"
            with mlflow.start_run(run_name=run_name):
                mlflow.log_param("target", target_name)
                mlflow.log_param("horizon", h)
                mlflow.log_param("train_end", train_end)
                mlflow.log_param("val_weeks", 8)
                mlflow.log_param("algo", "HistGradientBoostingRegressor")
                mlflow.log_param("grain", "ds_product_state")

                pipe.fit(X_train, y_train)

                # pred (volta do log)
                y_pred_log = pipe.predict(X_val)
                y_pred = np.expm1(y_pred_log)
                y_pred = np.clip(y_pred, 0, None)

                metrics = eval_metrics(y_val_true, y_pred)
                mlflow.log_metrics(metrics)

                # salva modelo
                model_name = f"{'demand' if 'qty' in target_name else 'cancel'}_product_region_h{h}"
                mlflow.sklearn.log_model(pipe, name="model")

                results.append({
                    "target": target_name,
                    "horizon": h,
                    **metrics,
                    "n_train": len(train_df),
                    "n_val": len(val_df),
                    "val_start": str(val_df["ds"].min().date()),
                    "val_end": str(val_df["ds"].max().date()),
                    "model_name": model_name,
                })

    return pd.DataFrame(results)

if __name__ == "__main__":
    df_res = train_all("data/olist.db", train_end="2018-08-26")
    print(df_res)
