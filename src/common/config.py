from __future__ import annotations

import os
from pathlib import Path


def _resolve_root() -> Path:
    env_root = os.getenv("WORKSPACE_ROOT")
    if env_root:
        return Path(env_root).expanduser().resolve()
    return Path(__file__).resolve().parents[2]


ROOT_DIR = _resolve_root()
DATA_DIR = ROOT_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
REFERENCE_DIR = DATA_DIR / "reference"
STREAM_INPUT_DIR = DATA_DIR / "stream_input"
DELTA_DIR = DATA_DIR / "delta"
CHECKPOINT_DIR = DELTA_DIR / "checkpoints"
MLFLOW_DIR = DATA_DIR / "mlflow"
REPORTS_DIR = DATA_DIR / "reports"

PAYSIM_CSV = RAW_DIR / "paysim.csv"
BLACKLIST_SEED_CSV = REFERENCE_DIR / "blacklist_seed.csv"

BRONZE_DIR = DELTA_DIR / "bronze"
SILVER_DIR = DELTA_DIR / "silver"
BLACKLIST_DIR = DELTA_DIR / "blacklist"
MODEL_DIR = DELTA_DIR / "model"
GOLD_SCORED_DIR = DELTA_DIR / "gold_scored"
GOLD_ALERTS_DIR = DELTA_DIR / "gold_alerts"
GOLD_METRICS_DIR = DELTA_DIR / "gold_metrics"

BRONZE_CHECKPOINT_DIR = CHECKPOINT_DIR / "bronze_stream"
SILVER_CHECKPOINT_DIR = CHECKPOINT_DIR / "silver_stream"
GOLD_CHECKPOINT_DIR = CHECKPOINT_DIR / "gold_stream"

APP_NAME = "FraudDetection"
SUPPORTED_MODEL_TYPES = ("TRANSFER", "CASH_OUT")
TYPE_TO_INDEX = {
    "CASH_IN": 0.0,
    "CASH_OUT": 1.0,
    "DEBIT": 2.0,
    "PAYMENT": 3.0,
    "TRANSFER": 4.0,
}
FEATURE_COLUMNS = [
    "amount",
    "oldbalanceorig",
    "newbalanceorig",
    "oldbalancedest",
    "newbalancedest",
    "error_balance_orig",
    "error_balance_dest",
    "amount_ratio",
    "is_zero_balance_after",
    "is_large_amount",
    "hour",
    "type_index",
]

LARGE_TXN_THRESHOLD = float(os.getenv("LARGE_TXN_THRESHOLD", "200000"))
BLACKLIST_BURST_THRESHOLD = int(os.getenv("BLACKLIST_BURST_THRESHOLD", "3"))
MAX_RULE_SCORE = 4.0
ML_WEIGHT = float(os.getenv("ML_WEIGHT", "0.7"))
RULE_WEIGHT = float(os.getenv("RULE_WEIGHT", "0.3"))
FINAL_THRESHOLD = float(os.getenv("FINAL_THRESHOLD", "0.5"))

SIMULATOR_BATCH_SIZE = int(os.getenv("SIMULATOR_BATCH_SIZE", "500"))
SIMULATOR_BATCHES = int(os.getenv("SIMULATOR_BATCHES", "15"))
SIMULATOR_SLEEP_SECONDS = float(os.getenv("SIMULATOR_SLEEP_SECONDS", "8"))
SIMULATOR_FRAUD_RATIO = float(os.getenv("SIMULATOR_FRAUD_RATIO", "0.15"))
BLACKLIST_SEED_LIMIT = int(os.getenv("BLACKLIST_SEED_LIMIT", "2000"))
TRAIN_NEGATIVE_RATIO = int(os.getenv("TRAIN_NEGATIVE_RATIO", "5"))

SPARK_MASTER = os.getenv("SPARK_MASTER", "local[2]")
SPARK_SHUFFLE_PARTITIONS = os.getenv("SPARK_SHUFFLE_PARTITIONS", "8")
SPARK_DRIVER_MEMORY = os.getenv("SPARK_DRIVER_MEMORY", "2g")
SPARK_OFFHEAP_SIZE = os.getenv("SPARK_OFFHEAP_SIZE", "512m")

STREAM_MAX_FILES_PER_TRIGGER = int(os.getenv("STREAM_MAX_FILES_PER_TRIGGER", "1"))
BRONZE_TRIGGER_INTERVAL = os.getenv("BRONZE_TRIGGER_INTERVAL", "10 seconds")
SILVER_TRIGGER_INTERVAL = os.getenv("SILVER_TRIGGER_INTERVAL", "10 seconds")
GOLD_TRIGGER_INTERVAL = os.getenv("GOLD_TRIGGER_INTERVAL", "10 seconds")

RUNTIME_DIRS = [
    RAW_DIR,
    REFERENCE_DIR,
    STREAM_INPUT_DIR,
    DELTA_DIR,
    CHECKPOINT_DIR,
    BRONZE_CHECKPOINT_DIR,
    SILVER_CHECKPOINT_DIR,
    GOLD_CHECKPOINT_DIR,
    MLFLOW_DIR,
    REPORTS_DIR,
]


def ensure_runtime_dirs() -> None:
    for path in RUNTIME_DIRS:
        path.mkdir(parents=True, exist_ok=True)


def path_to_str(path: Path) -> str:
    return path.resolve().as_posix()


def path_to_uri(path: Path) -> str:
    return path.resolve().as_uri()


def delta_table_exists(path: Path) -> bool:
    return (path / "_delta_log").exists()


PATHS = {
    "raw_csv": path_to_str(PAYSIM_CSV),
    "blacklist_seed_csv": path_to_str(BLACKLIST_SEED_CSV),
    "stream_input": path_to_str(STREAM_INPUT_DIR),
    "bronze": path_to_str(BRONZE_DIR),
    "silver": path_to_str(SILVER_DIR),
    "blacklist": path_to_str(BLACKLIST_DIR),
    "model": path_to_str(MODEL_DIR),
    "gold_scored": path_to_str(GOLD_SCORED_DIR),
    "gold_alerts": path_to_str(GOLD_ALERTS_DIR),
    "gold_metrics": path_to_str(GOLD_METRICS_DIR),
    "bronze_checkpoint": path_to_str(BRONZE_CHECKPOINT_DIR),
    "silver_checkpoint": path_to_str(SILVER_CHECKPOINT_DIR),
    "gold_checkpoint": path_to_str(GOLD_CHECKPOINT_DIR),
    "mlflow": path_to_str(MLFLOW_DIR),
    "reports": path_to_str(REPORTS_DIR),
}
