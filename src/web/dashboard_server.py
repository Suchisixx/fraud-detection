from __future__ import annotations

import argparse
import csv
import json
import mimetypes
import os
from collections import Counter
from datetime import datetime, timezone
from functools import partial
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Lock
from time import monotonic
from urllib.parse import unquote, urlsplit

from src.common.config import (
    BRONZE_DIR,
    GOLD_ALERTS_DIR,
    GOLD_SCORED_DIR,
    PAYSIM_CSV,
    PATHS,
    REPORTS_DIR,
    SILVER_DIR,
    STREAM_INPUT_DIR,
    SUPPORTED_MODEL_TYPES,
    delta_table_exists,
)

STATIC_DIR = Path(__file__).resolve().parent / "static"
DEFAULT_HOST = os.getenv("DASHBOARD_HOST", "127.0.0.1")
DEFAULT_PORT = int(os.getenv("DASHBOARD_PORT", "8008"))
LAYER_CACHE_TTL_SECONDS = float(os.getenv("DASHBOARD_LAYER_CACHE_TTL", "15"))
_LAYER_CACHE_LOCK = Lock()
_LAYER_CACHE: dict[str, object] = {"expires_at": 0.0, "payload": None}
_LAYER_WARNINGS_EMITTED: set[str] = set()


def _read_json_file(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return None


def _read_csv_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as fh:
            return list(csv.DictReader(fh))
    except OSError:
        return []


def _as_float(value: object, digits: int = 4) -> float | None:
    if value in (None, ""):
        return None
    try:
        return round(float(value), digits)
    except (TypeError, ValueError):
        return None


def _as_int(value: object) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _metric(source: dict | None, *keys: str, digits: int = 4) -> float | None:
    if not source:
        return None
    for key in keys:
        if key in source:
            return _as_float(source.get(key), digits=digits)
    return None


def _summary_payload(latest_batch: dict | None) -> dict:
    latest_batch = latest_batch or {}
    return {
        "batch_id": _as_int(latest_batch.get("batch_id") or latest_batch.get("ma_lo")),
        "rows": _as_int(latest_batch.get("rows") or latest_batch.get("so_dong")),
        "alerts": _as_int(latest_batch.get("alerts") or latest_batch.get("so_canh_bao")),
        "latency_ms": _as_int(latest_batch.get("latency_ms") or latest_batch.get("thoi_gian_ms")),
    }


def _training_payload(training_metrics: dict | None) -> dict:
    return {
        "auc_roc": _metric(training_metrics, "auc_roc"),
        "auc_pr": _metric(training_metrics, "auc_pr"),
        "accuracy": _metric(training_metrics, "accuracy", "do_chinh_xac"),
        "precision": _metric(training_metrics, "precision"),
        "recall": _metric(training_metrics, "recall"),
        "f1": _metric(training_metrics, "f1"),
    }


def _evaluation_payload(rows: list[dict]) -> list[dict]:
    payload: list[dict] = []
    for row in rows:
        payload.append(
            {
                "model": row.get("model") or row.get("mo_hinh") or "Chưa rõ",
                "precision": _as_float(row.get("precision")),
                "recall": _as_float(row.get("recall")),
                "f1": _as_float(row.get("f1")),
            }
        )
    return payload


def _top_risk_payload(rows: list[dict]) -> list[dict]:
    payload: list[dict] = []
    for row in rows[:20]:
        payload.append(
            {
                "account": row.get("account") or row.get("nameorig") or row.get("account_id") or "N/A",
                "alert_count": _as_int(row.get("alert_count")),
                "total_amount": _as_float(row.get("total_amount"), digits=2),
                "avg_score": _as_float(row.get("avg_score")),
            }
        )
    return payload


def _report_file_payload() -> list[dict]:
    payload: list[dict] = []
    if not REPORTS_DIR.exists():
        return payload

    for path in sorted(REPORTS_DIR.iterdir()):
        if not path.is_file():
            continue
        try:
            stat = path.stat()
        except OSError:
            continue
        payload.append(
            {
                "name": path.name,
                "size_bytes": stat.st_size,
                "updated_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).astimezone().isoformat(),
            }
        )
    return payload


def _layer_card(
    *,
    layer_id: str,
    title: str,
    storage: str,
    count: int | None,
    unit: str,
    column_count: int | None,
    transition: str,
    highlights: list[str],
    metrics: list[dict],
    progress: dict | None = None,
) -> dict:
    return {
        "id": layer_id,
        "title": title,
        "storage": storage,
        "count": count,
        "unit": unit,
        "column_count": column_count,
        "transition": transition,
        "highlights": highlights,
        "metrics": metrics,
        "progress": progress,
    }


def _stream_batch_count() -> int | None:
    if not STREAM_INPUT_DIR.exists():
        return None
    try:
        return sum(1 for path in STREAM_INPUT_DIR.iterdir() if path.is_dir())
    except OSError:
        return None


def _safe_ratio(numerator: int | None, denominator: int | None, digits: int = 4) -> float | None:
    if numerator is None or denominator in (None, 0):
        return None
    return round(numerator / denominator, digits)


def _emit_layer_warning_once(key: str, message: str) -> None:
    if key in _LAYER_WARNINGS_EMITTED:
        return
    _LAYER_WARNINGS_EMITTED.add(key)
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[dashboard {timestamp}] {message}")


def _csv_row_count(path: Path) -> int | None:
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as fh:
            reader = csv.reader(fh)
            next(reader, None)
            return sum(1 for _ in reader)
    except OSError:
        return None


def _delta_json_log_files(table_dir: Path) -> list[Path]:
    log_dir = table_dir / "_delta_log"
    if not log_dir.exists():
        return []
    return sorted(
        path
        for path in log_dir.iterdir()
        if path.is_file() and path.suffix == ".json" and path.stem.isdigit()
    )


def _delta_schema_column_count(table_dir: Path) -> int | None:
    for log_path in _delta_json_log_files(table_dir):
        try:
            with log_path.open("r", encoding="utf-8") as fh:
                for line in fh:
                    payload = json.loads(line)
                    metadata = payload.get("metaData")
                    if not metadata:
                        continue
                    schema_string = metadata.get("schemaString")
                    if not schema_string:
                        continue
                    schema_json = json.loads(schema_string)
                    return len(schema_json.get("fields", []))
        except (OSError, json.JSONDecodeError):
            continue
    return None


def _delta_log_snapshot(table_dir: Path) -> dict:
    counts_by_file: dict[str, int] = {}
    counts_by_partition: Counter[str] = Counter()
    null_counts = Counter()
    min_values: dict[str, float] = {}
    max_values: dict[str, float] = {}

    for log_path in _delta_json_log_files(table_dir):
        try:
            with log_path.open("r", encoding="utf-8") as fh:
                for line in fh:
                    payload = json.loads(line)
                    add = payload.get("add")
                    if add:
                        stats_raw = add.get("stats")
                        stats = json.loads(stats_raw) if isinstance(stats_raw, str) and stats_raw else {}
                        num_records = int(stats.get("numRecords", 0))
                        counts_by_file[add.get("path", "")] = num_records

                        partition_values = add.get("partitionValues") or {}
                        partition_type = partition_values.get("type")
                        if partition_type:
                            counts_by_partition[partition_type] += num_records

                        for key, value in (stats.get("nullCount") or {}).items():
                            null_counts[key] += int(value or 0)

                        for key, value in (stats.get("minValues") or {}).items():
                            if isinstance(value, (int, float)):
                                min_values[key] = min(value, min_values.get(key, value))

                        for key, value in (stats.get("maxValues") or {}).items():
                            if isinstance(value, (int, float)):
                                max_values[key] = max(value, max_values.get(key, value))
                        continue

                    remove = payload.get("remove")
                    if remove:
                        removed_path = remove.get("path", "")
                        removed_records = counts_by_file.pop(removed_path, 0)
                        partition_hint = removed_path.split("/")[0]
                        if partition_hint.startswith("type="):
                            counts_by_partition[partition_hint.removeprefix("type=")] -= removed_records
        except (OSError, json.JSONDecodeError, ValueError, TypeError):
            continue

    total_rows = sum(max(value, 0) for value in counts_by_file.values())
    counts_by_partition = Counter({key: value for key, value in counts_by_partition.items() if value > 0})
    return {
        "rows": total_rows,
        "files": len(counts_by_file),
        "partitions": dict(counts_by_partition),
        "null_counts": dict(null_counts),
        "min_values": min_values,
        "max_values": max_values,
    }


def _compute_layer_payload() -> dict:
    evaluation_rows = _read_csv_rows(REPORTS_DIR / "evaluation_summary.csv")
    top_risk_rows = _read_csv_rows(REPORTS_DIR / "top_risk_accounts.csv")
    report_files = _report_file_payload()
    latest_batch = _read_json_file(REPORTS_DIR / "latest_gold_batch.json") or {}
    stream_batches = _stream_batch_count()

    try:
        from pyspark.sql import functions as F

        from src.common.spark import get_spark
    except Exception as exc:
        _emit_layer_warning_once(
            "delta-log-fallback",
            f"Dashboard dang dung che do fallback vi chua nap duoc Spark/Delta: {exc}",
        )
        raw_count = _csv_row_count(PAYSIM_CSV)
        bronze_snapshot = _delta_log_snapshot(BRONZE_DIR) if delta_table_exists(BRONZE_DIR) else {}
        silver_snapshot = _delta_log_snapshot(SILVER_DIR) if delta_table_exists(SILVER_DIR) else {}
        gold_snapshot = _delta_log_snapshot(GOLD_SCORED_DIR) if delta_table_exists(GOLD_SCORED_DIR) else {}
        gold_alert_snapshot = _delta_log_snapshot(GOLD_ALERTS_DIR) if delta_table_exists(GOLD_ALERTS_DIR) else {}

        bronze_count = bronze_snapshot.get("rows")
        silver_count = silver_snapshot.get("rows")
        gold_count = gold_snapshot.get("rows")
        cleaned_out_rows = None
        if isinstance(bronze_count, int) and isinstance(silver_count, int):
            cleaned_out_rows = bronze_count - silver_count

        return {
            "available": False,
            "source": "delta-log-fallback",
            "message": None,
            "items": [
                _layer_card(
                    layer_id="raw",
                    title="Raw",
                    storage="CSV lịch sử",
                    count=raw_count,
                    unit="dòng",
                    column_count=11,
                    transition="Nguồn đầu vào gốc",
                    highlights=[
                        "Dữ liệu PaySim ban đầu trong paysim.csv.",
                        "Chưa có txn_id, metadata stream, feature hay rule.",
                        "Dùng cho seed blacklist, train model và mô phỏng stream.",
                    ],
                    metrics=[
                        {"label": "Batch mô phỏng", "value": stream_batches, "unit": "batch"},
                    ],
                ),
                _layer_card(
                    layer_id="bronze",
                    title="Bronze",
                    storage="Delta Lake",
                    count=bronze_count,
                    unit="dòng",
                    column_count=_delta_schema_column_count(BRONZE_DIR) or 14,
                    transition="+ chuẩn hóa cột + metadata stream",
                    highlights=[
                        "Đổi tên cột về convention nội bộ.",
                        "Thêm txn_id, ingested_at, source_file.",
                        "So dong dang duoc doc tu Delta log, khong can Spark.",
                    ],
                    metrics=[
                        {"label": "File nguon da ingest", "value": bronze_snapshot.get("files"), "unit": "file"},
                        {"label": "Batch mo phong", "value": stream_batches, "unit": "batch"},
                    ],
                    progress={
                        "label": "Da ingest so voi Raw",
                        "ratio": _safe_ratio(bronze_count, raw_count),
                    },
                ),
                _layer_card(
                    layer_id="silver",
                    title="Silver",
                    storage="Delta Lake",
                    count=silver_count,
                    unit="dòng",
                    column_count=_delta_schema_column_count(SILVER_DIR) or 28,
                    transition="- dòng lỗi/trùng + feature + rule",
                    highlights=[
                        "Làm sạch dữ liệu và bỏ dòng không hợp lệ.",
                        "Bổ sung feature engineering và rule-based detection.",
                        "So dong dang duoc doc tu Delta log, khong can Spark.",
                    ],
                    metrics=[
                        {"label": "Dong bi loai sau clean", "value": cleaned_out_rows, "unit": "dòng"},
                        {"label": "Loai giao dich con lai", "value": len(silver_snapshot.get("partitions", {})), "unit": "loại"},
                    ],
                    progress={
                        "label": "Giu lai sau Bronze",
                        "ratio": _safe_ratio(silver_count, bronze_count),
                    },
                ),
                _layer_card(
                    layer_id="gold",
                    title="Gold",
                    storage="Delta Lake",
                    count=gold_count,
                    unit="dòng",
                    column_count=_delta_schema_column_count(GOLD_SCORED_DIR),
                    transition="+ ML score + composite score + final alert",
                    highlights=[
                        "Kết hợp Rule + ML để chấm điểm cuối.",
                        "Sinh final_alert và alert_reason.",
                        "So dong dang duoc doc tu Delta log, khong can Spark.",
                    ],
                    metrics=[
                        {"label": "Gold alerts table", "value": gold_alert_snapshot.get("rows"), "unit": "dòng"},
                        {"label": "Batch Gold moi nhat", "value": _as_int(latest_batch.get("ma_lo") or latest_batch.get("batch_id")), "unit": "lô"},
                    ],
                    progress={
                        "label": "Da cham diem so voi Silver",
                        "ratio": _safe_ratio(gold_count, silver_count),
                    },
                ),
                _layer_card(
                    layer_id="reports",
                    title="Reports",
                    storage="CSV / JSON / PNG",
                    count=len(report_files),
                    unit="tệp",
                    column_count=None,
                    transition="Tổng hợp thành artifact phục vụ demo",
                    highlights=[
                        "Không giữ giao dịch thô mà lưu file tổng hợp.",
                        f"Có {len(evaluation_rows)} dòng evaluation và {len(top_risk_rows)} dòng top risk.",
                        "Dashboard image, metrics, summary được đọc trực tiếp từ thư mục reports.",
                    ],
                    metrics=[
                        {"label": "Artifacts", "value": len(report_files), "unit": "tệp"},
                        {"label": "Top risk rows", "value": len(top_risk_rows), "unit": "dòng"},
                    ],
                ),
            ],
            "report_files": report_files,
        }

    if not PAYSIM_CSV.exists():
        _emit_layer_warning_once("missing-raw", f"Khong tim thay du lieu Raw tai {PAYSIM_CSV}")
        return {
            "available": False,
            "source": "reports-only",
            "message": None,
            "items": [],
            "report_files": report_files,
        }

    spark = get_spark("DashboardLayerStats")

    raw_df = spark.read.option("header", "true").csv(PAYSIM_CSV.as_posix())
    raw_stats = raw_df.agg(
        F.count("*").alias("rows"),
        F.sum(F.when(F.col("isFraud") == "1", 1).otherwise(0)).alias("fraud_rows"),
        F.countDistinct("type").alias("type_count"),
    ).first()
    raw_count = int(raw_stats.rows)
    raw_fraud_rows = int(raw_stats.fraud_rows or 0)
    raw_type_count = int(raw_stats.type_count or 0)

    bronze_df = spark.read.format("delta").load(PATHS["bronze"]) if delta_table_exists(BRONZE_DIR) else None
    bronze_count = None
    bronze_columns = None
    bronze_invalid_rows = None
    bronze_missing_origin = None
    bronze_missing_dest = None
    bronze_duplicate_rows = None
    bronze_source_files = None
    if bronze_df is not None:
        bronze_columns = len(bronze_df.columns)
        bronze_stats = bronze_df.agg(
            F.count("*").alias("rows"),
            F.sum(F.when(F.col("amount") <= 0, 1).otherwise(0)).alias("invalid_rows"),
            F.sum(F.when(F.col("nameorig").isNull(), 1).otherwise(0)).alias("missing_origin"),
            F.sum(F.when(F.col("namedest").isNull(), 1).otherwise(0)).alias("missing_dest"),
            F.countDistinct("txn_id").alias("distinct_txn"),
            F.countDistinct("source_file").alias("source_files"),
        ).first()
        bronze_count = int(bronze_stats.rows)
        bronze_invalid_rows = int(bronze_stats.invalid_rows or 0)
        bronze_missing_origin = int(bronze_stats.missing_origin or 0)
        bronze_missing_dest = int(bronze_stats.missing_dest or 0)
        bronze_duplicate_rows = bronze_count - int(bronze_stats.distinct_txn or 0)
        bronze_source_files = int(bronze_stats.source_files or 0)

    silver_df = spark.read.format("delta").load(PATHS["silver"]) if delta_table_exists(SILVER_DIR) else None
    silver_count = None
    silver_columns = None
    silver_rule_alerts = None
    silver_blacklist_hits = None
    silver_burst_hits = None
    silver_avg_rule_score = None
    if silver_df is not None:
        silver_columns = len(silver_df.columns)
        silver_stats = silver_df.agg(
            F.count("*").alias("rows"),
            F.sum(F.when(F.col("rule_alert") == 1, 1).otherwise(0)).alias("rule_alerts"),
            F.sum(F.when(F.col("rule_blacklist") == 1, 1).otherwise(0)).alias("blacklist_hits"),
            F.sum(F.when(F.col("rule_blacklist_burst") == 1, 1).otherwise(0)).alias("burst_hits"),
            F.avg("rule_score_normalized").alias("avg_rule_score"),
        ).first()
        silver_count = int(silver_stats.rows)
        silver_rule_alerts = int(silver_stats.rule_alerts or 0)
        silver_blacklist_hits = int(silver_stats.blacklist_hits or 0)
        silver_burst_hits = int(silver_stats.burst_hits or 0)
        silver_avg_rule_score = _as_float(silver_stats.avg_rule_score)

    gold_df = spark.read.format("delta").load(PATHS["gold_scored"]) if delta_table_exists(GOLD_SCORED_DIR) else None
    gold_count = None
    gold_columns = None
    gold_alert_rows = None
    gold_ml_scope_rows = None
    gold_avg_ml_probability = None
    gold_avg_composite = None
    if gold_df is not None:
        gold_columns = len(gold_df.columns)
        gold_stats = gold_df.agg(
            F.count("*").alias("rows"),
            F.sum(F.when(F.col("final_alert") == 1, 1).otherwise(0)).alias("alert_rows"),
            F.sum(F.when(F.upper(F.col("type")).isin(*SUPPORTED_MODEL_TYPES), 1).otherwise(0)).alias("ml_scope_rows"),
            F.avg("ml_probability").alias("avg_ml_probability"),
            F.avg("composite_score").alias("avg_composite"),
        ).first()
        gold_count = int(gold_stats.rows)
        gold_alert_rows = int(gold_stats.alert_rows or 0)
        gold_ml_scope_rows = int(gold_stats.ml_scope_rows or 0)
        gold_avg_ml_probability = _as_float(gold_stats.avg_ml_probability)
        gold_avg_composite = _as_float(gold_stats.avg_composite)

    gold_alert_table_rows = None
    if delta_table_exists(GOLD_ALERTS_DIR):
        gold_alerts_df = spark.read.format("delta").load(PATHS["gold_alerts"])
        gold_alert_table_rows = int(gold_alerts_df.count())

    bronze_progress = _safe_ratio(bronze_count, raw_count)
    silver_progress = _safe_ratio(silver_count, bronze_count)
    gold_progress = _safe_ratio(gold_count, silver_count)
    cleaned_out_rows = None
    if bronze_count is not None and silver_count is not None:
        cleaned_out_rows = bronze_count - silver_count

    items = [
        _layer_card(
            layer_id="raw",
            title="Raw",
            storage="CSV lịch sử",
            count=raw_count,
            unit="dòng",
            column_count=len(raw_df.columns),
            transition="Nguồn PaySim gốc trước khi vào pipeline",
            highlights=[
                "Giữ nguyên schema PaySim với nhãn isFraud / isFlaggedFraud.",
                "Chưa có txn_id, metadata stream, feature hay rule.",
                f"Đã chia thành {stream_batches or 0} batch mô phỏng để đẩy vào luồng online.",
            ],
            metrics=[
                {"label": "Giao dịch fraud đã biết", "value": raw_fraud_rows, "unit": "dòng"},
                {"label": "Loại giao dịch", "value": raw_type_count, "unit": "loại"},
                {"label": "Batch mô phỏng", "value": stream_batches, "unit": "batch"},
            ],
        ),
        _layer_card(
            layer_id="bronze",
            title="Bronze",
            storage="Delta Lake",
            count=bronze_count,
            unit="dòng",
            column_count=bronze_columns,
            transition="+ chuẩn hóa cột + txn_id + metadata ingest",
            highlights=[
                "Đổi tên cột về convention nội bộ để các job dùng chung logic.",
                "Thêm txn_id, ingested_at, source_file để truy vết theo batch stream.",
                "Số dòng ở Bronze phản ánh tiến độ ingest, nên có thể nhỏ hơn Raw khi stream chưa chạy hết.",
            ],
            metrics=[
                {"label": "Dòng amount <= 0", "value": bronze_invalid_rows, "unit": "dòng"},
                {"label": "Thiếu source/dest", "value": (bronze_missing_origin or 0) + (bronze_missing_dest or 0), "unit": "dòng"},
                {"label": "Txn trùng tiềm năng", "value": bronze_duplicate_rows, "unit": "dòng"},
                {"label": "File nguồn đã ingest", "value": bronze_source_files, "unit": "file"},
            ],
            progress={
                "label": "Đã ingest so với Raw",
                "ratio": bronze_progress,
            },
        ),
        _layer_card(
            layer_id="silver",
            title="Silver",
            storage="Delta Lake",
            count=silver_count,
            unit="dòng",
            column_count=silver_columns,
            transition="- dòng lỗi/trùng + feature engineering + rule engine",
            highlights=[
                "Loại bỏ giao dịch amount <= 0, thiếu tài khoản hoặc trùng txn_id.",
                "Bổ sung feature: error_balance_*, amount_ratio, is_zero_balance_after, hour, type_index.",
                "Gắn cờ rule_blacklist, rule_large_txn, rule_drain, rule_blacklist_burst để chuẩn bị cho Gold.",
            ],
            metrics=[
                {"label": "Dòng bị loại sau clean", "value": cleaned_out_rows, "unit": "dòng"},
                {"label": "Rule alert", "value": silver_rule_alerts, "unit": "dòng"},
                {"label": "Chạm blacklist", "value": silver_blacklist_hits, "unit": "dòng"},
                {"label": "Avg rule score", "value": silver_avg_rule_score, "unit": None},
            ],
            progress={
                "label": "Giữ lại sau Bronze",
                "ratio": silver_progress,
            },
        ),
        _layer_card(
            layer_id="gold",
            title="Gold",
            storage="Delta Lake",
            count=gold_count,
            unit="dòng",
            column_count=gold_columns,
            transition="+ ML probability + composite score + final alert",
            highlights=[
                "Chỉ dùng ML cho TRANSFER và CASH_OUT, còn lại fallback theo rule.",
                "Thêm ml_probability, ml_prediction, composite_score, final_alert, alert_reason.",
                "Gold là tầng quyết định cuối cùng trước khi sinh reports và dashboard.",
            ],
            metrics=[
                {"label": "Final alert", "value": gold_alert_rows, "unit": "dòng"},
                {"label": "Trong scope ML", "value": gold_ml_scope_rows, "unit": "dòng"},
                {"label": "Gold alerts table", "value": gold_alert_table_rows, "unit": "dòng"},
                {"label": "Avg composite", "value": gold_avg_composite, "unit": None},
            ],
            progress={
                "label": "Đã chấm điểm so với Silver",
                "ratio": gold_progress,
            },
        ),
        _layer_card(
            layer_id="reports",
            title="Reports",
            storage="CSV / JSON / PNG",
            count=len(report_files),
            unit="tệp",
            column_count=None,
            transition="Tổng hợp thành artifact phục vụ thuyết trình",
            highlights=[
                "Không còn giữ toàn bộ giao dịch, mà lưu file báo cáo, metrics và ảnh dashboard.",
                "Bao gồm training_metrics.json, evaluation_summary.csv, top_risk_accounts.csv, latest_gold_batch.json, dashboard.png.",
                "Đây là tầng trình bày kết quả cho demo và bảo vệ đồ án.",
            ],
            metrics=[
                {"label": "Artifacts", "value": len(report_files), "unit": "tệp"},
                {"label": "Evaluation rows", "value": len(evaluation_rows), "unit": "dòng"},
                {"label": "Top risk rows", "value": len(top_risk_rows), "unit": "dòng"},
                {"label": "Batch Gold mới nhất", "value": _as_int(latest_batch.get("ma_lo") or latest_batch.get("batch_id")), "unit": "lô"},
            ],
        ),
    ]

    return {
        "available": True,
        "source": "spark",
        "message": None,
        "items": items,
        "report_files": report_files,
    }


def _layer_payload() -> dict:
    with _LAYER_CACHE_LOCK:
        now = monotonic()
        cached_payload = _LAYER_CACHE.get("payload")
        if cached_payload is not None and now < float(_LAYER_CACHE.get("expires_at", 0.0)):
            return cached_payload

        payload = _compute_layer_payload()
        _LAYER_CACHE["payload"] = payload
        _LAYER_CACHE["expires_at"] = now + LAYER_CACHE_TTL_SECONDS
        return payload


def build_dashboard_payload() -> dict:
    latest_batch_path = REPORTS_DIR / "latest_gold_batch.json"
    training_metrics_path = REPORTS_DIR / "training_metrics.json"
    evaluation_path = REPORTS_DIR / "evaluation_summary.csv"
    top_risk_path = REPORTS_DIR / "top_risk_accounts.csv"
    dashboard_image_path = REPORTS_DIR / "dashboard.png"

    latest_batch = _read_json_file(latest_batch_path)
    training_metrics = _read_json_file(training_metrics_path)
    evaluation_rows = _read_csv_rows(evaluation_path)
    top_risk_rows = _read_csv_rows(top_risk_path)
    layer_payload = _layer_payload()

    status = {
        "has_latest_batch": latest_batch is not None,
        "has_training_metrics": training_metrics is not None,
        "has_evaluation": bool(evaluation_rows),
        "has_top_risk_accounts": bool(top_risk_rows),
        "has_dashboard_image": dashboard_image_path.exists(),
    }

    return {
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(),
        "summary": _summary_payload(latest_batch),
        "training": _training_payload(training_metrics),
        "evaluation": _evaluation_payload(evaluation_rows),
        "top_risk_accounts": _top_risk_payload(top_risk_rows),
        "layers": layer_payload,
        "assets": {
            "dashboard_image_url": "/reports/dashboard.png" if dashboard_image_path.exists() else None,
        },
        "status": status,
    }


class DashboardRequestHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, directory: str | None = None, reports_dir: str | None = None, **kwargs):
        self.reports_dir = Path(reports_dir or REPORTS_DIR).resolve()
        super().__init__(*args, directory=directory, **kwargs)

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def do_GET(self) -> None:
        parsed = urlsplit(self.path)
        path = unquote(parsed.path)

        if path == "/api/dashboard":
            self._serve_dashboard_api()
            return

        if path.startswith("/reports/"):
            self._serve_report_asset(path)
            return

        if path == "/":
            self.path = "/index.html"
        else:
            self.path = path
        super().do_GET()

    def log_message(self, format: str, *args) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[dashboard {timestamp}] {format % args}")

    def _serve_dashboard_api(self) -> None:
        payload = build_dashboard_payload()
        encoded = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _serve_report_asset(self, request_path: str) -> None:
        relative_path = request_path.removeprefix("/reports/")
        candidate = (self.reports_dir / relative_path).resolve()

        if self.reports_dir not in candidate.parents and candidate != self.reports_dir:
            self.send_error(HTTPStatus.FORBIDDEN, "Đường dẫn không hợp lệ.")
            return

        if not candidate.exists() or not candidate.is_file():
            self.send_error(HTTPStatus.NOT_FOUND, "Không tìm thấy file báo cáo.")
            return

        mime_type, _ = mimetypes.guess_type(candidate.as_posix())
        try:
            with candidate.open("rb") as fh:
                content = fh.read()
        except OSError:
            self.send_error(HTTPStatus.INTERNAL_SERVER_ERROR, "Không thể đọc file báo cáo.")
            return

        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", mime_type or "application/octet-stream")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Chạy dashboard demo cho đồ án Big Data.")
    parser.add_argument("--host", default=DEFAULT_HOST, help=f"Host phục vụ dashboard. Mặc định: {DEFAULT_HOST}")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"Port phục vụ dashboard. Mặc định: {DEFAULT_PORT}")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    handler = partial(
        DashboardRequestHandler,
        directory=STATIC_DIR.as_posix(),
        reports_dir=REPORTS_DIR.as_posix(),
    )
    server = ThreadingHTTPServer((args.host, args.port), handler)
    print(f"Dashboard đang chạy tại http://{args.host}:{args.port}")
    print("Nhấn Ctrl+C để dừng server.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nĐã dừng dashboard server.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
