import argparse
import os

from src.extract_load import load_all
from src.run_sql import run_all
from src.train import train_all
from src.predict import predict_all
from src.monitor import monitor
from src.export_powerbi import export_all

DB_PATH = os.path.join("data", "olist.db")

def main(train_end: str, as_of_ds: str, rebuild_staging: bool = True):
    print("=== 1) EXTRAÇÃO/LOAD (staging) ===")
    load_all(db_path=DB_PATH, rebuild=rebuild_staging)

    print("=== 2) FEATURE STORE (SQL) ===")
    run_all(DB_PATH)

    print("=== 3) TREINO + MLFLOW ===")
    metrics_df = train_all(DB_PATH, train_end=train_end)
    metrics_df.to_csv("exports/metrics_training_summary.csv", index=False)
    print("[OK] metrics_training_summary.csv gerado.")

    print("=== 4) PREDIÇÃO ===")
    predict_all(DB_PATH, as_of_ds=as_of_ds)

    print("=== 5) MONITORAMENTO ===")
    monitor(DB_PATH, as_of_ds=as_of_ds)

    print("=== 6) EXPORT POWER BI ===")
    export_all(DB_PATH)

    print("=== FIM ===")
# data --train_end 2019-06-30 --as_of_ds 2019-06-30

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--train_end", required=True, help="Data final (YYYY-MM-DD) para treino/val")
    parser.add_argument("--as_of_ds", required=True, help="Data base (YYYY-MM-DD) para inferência")
    parser.add_argument("--rebuild_staging", action="store_true", help="Recria staging do zero")
    args = parser.parse_args()

    main(train_end=args.train_end, as_of_ds=args.as_of_ds, rebuild_staging=args.rebuild_staging)
