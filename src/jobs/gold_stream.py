from __future__ import annotations

import json
import time

import matplotlib.pyplot as plt
import pandas as pd
from pyspark.ml import PipelineModel
from pyspark.ml.functions import vector_to_array
from pyspark.sql import DataFrame, functions as F
from sklearn.metrics import f1_score, precision_score, recall_score

from src.common.config import (
    FINAL_THRESHOLD,
    GOLD_SCORED_DIR,
    GOLD_TRIGGER_INTERVAL,
    ML_WEIGHT,
    MODEL_DIR,
    PATHS,
    REPORTS_DIR,
    RULE_WEIGHT,
    SUPPORTED_MODEL_TYPES,
    delta_table_exists,
    ensure_runtime_dirs,
)
from src.common.schemas import SILVER_SCHEMA
from src.common.spark import ensure_delta_table, get_spark

"""
Vai trò:
- Tầng Gold: kết hợp rule-based và machine learning để sinh cảnh báo cuối cùng.
- Đồng thời tạo metrics và dashboard cho phần demo / báo cáo.

Liên hệ tiêu chí:
- Độ chính xác và giá trị thực tiễn: đây là lớp hybrid detection.
- Hình thức báo cáo và giải trình: đây là nơi sinh dashboard, evaluation summary,
  top risk accounts và bảng alerts để trình bày với giảng viên.
"""


def _score_batch(model: PipelineModel, batch_df: DataFrame) -> DataFrame:
    """
    Kết hợp AI + Rule:
    - ML cho các loại giao dịch trọng tâm.
    - Rule score lấy từ Silver.
    - Composite score dùng để ra final alert.
    """
    base_columns = batch_df.columns
    model_scope = batch_df.filter(F.upper(F.col("type")).isin(*SUPPORTED_MODEL_TYPES))
    rule_only_scope = batch_df.filter(~F.upper(F.col("type")).isin(*SUPPORTED_MODEL_TYPES))

    scored_scope = (
        model.transform(model_scope)
        .withColumn("ml_probability", vector_to_array(F.col("probability"))[1])
        .withColumn("ml_prediction", F.when(F.col("ml_probability") >= 0.5, 1).otherwise(0))
        .select(*base_columns, "ml_probability", "ml_prediction")
    )

    fallback_scope = (
        rule_only_scope.select(*base_columns)
        .withColumn("ml_probability", F.lit(0.0))
        .withColumn("ml_prediction", F.lit(0))
    )

    # Đây là công thức hybrid cốt lõi của đồ án.
    return (
        scored_scope.unionByName(fallback_scope)
        .withColumn(
            "composite_score",
            F.round(
                F.col("ml_probability") * F.lit(ML_WEIGHT)
                + F.col("rule_score_normalized") * F.lit(RULE_WEIGHT),
                4,
            ),
        )
        .withColumn(
            "final_alert",
            F.when(
                (F.col("composite_score") >= FINAL_THRESHOLD)
                | (F.col("rule_blacklist") == 1)
                | (F.col("rule_blacklist_burst") == 1),
                1,
            ).otherwise(0),
        )
        .withColumn("scored_at", F.current_timestamp())
        .withColumn(
            "alert_reason",
            F.concat_ws(
                ", ",
                F.when(F.col("rule_blacklist") == 1, F.lit("CHAM_DANH_SACH_DEN")),
                F.when(F.col("rule_blacklist_burst") == 1, F.lit("CHUYEN_LIEN_TUC_VAO_BLACKLIST")),
                F.when(F.col("rule_large_txn") == 1, F.lit("GIAO_DICH_LON")),
                F.when(F.col("rule_drain") == 1, F.lit("RUT_CAN_SACH_TAI_KHOAN")),
                F.when(F.col("ml_prediction") == 1, F.lit("MO_HINH_DANH_GIA_RUI_RO_CAO")),
            ),
        )
    )


def _render_dashboard(spark) -> None:
    """Đọc Gold đã chấm điểm để tạo dashboard và file báo cáo phụ trợ."""
    if not delta_table_exists(GOLD_SCORED_DIR):
        return

    scored = spark.read.format("delta").load(PATHS["gold_scored"])
    if scored.isEmpty():
        return

    eval_pd = scored.select(
        "type",
        "amount",
        "hour",
        "isfraud",
        "rule_alert",
        "ml_prediction",
        "final_alert",
        "ml_probability",
        "composite_score",
    ).toPandas()
    y_true = eval_pd["isfraud"]

    # So sánh 3 cách phát hiện: Rule, ML, Hybrid.
    metrics_rows = []
    for column_name, label in [("rule_alert", "Luật"), ("ml_prediction", "Máy học"), ("final_alert", "Lai")]:
        metrics_rows.append(
            {
                "mo_hinh": label,
                "precision": precision_score(y_true, eval_pd[column_name], zero_division=0),
                "recall": recall_score(y_true, eval_pd[column_name], zero_division=0),
                "f1": f1_score(y_true, eval_pd[column_name], zero_division=0),
            }
        )
    metrics_pd = pd.DataFrame(metrics_rows)
    metrics_pd.to_csv((REPORTS_DIR / "evaluation_summary.csv").as_posix(), index=False)

    fig, axes = plt.subplots(2, 3, figsize=(16, 9))
    fig.suptitle("Dashboard Phát Hiện Gian Lận Thời Gian Thực - PaySim", fontsize=13, fontweight="bold")

    fraud_counts = eval_pd["isfraud"].value_counts().reindex([0, 1], fill_value=0)
    axes[0, 0].pie(
        fraud_counts.values,
        labels=["Bình thường", "Gian lận"],
        colors=["#60a5fa", "#f97316"],
        autopct="%1.2f%%",
        startangle=90,
    )
    axes[0, 0].set_title("Tỷ Lệ Gian Lận")

    txn_stats = (
        eval_pd.groupby("type")
        .agg(total=("type", "count"), alerts=("final_alert", "sum"))
        .sort_values("total", ascending=False)
        .reset_index()
    )
    axes[0, 1].bar(txn_stats["type"], txn_stats["total"], label="Tổng giao dịch", color="#0ea5e9", alpha=0.8)
    axes[0, 1].bar(txn_stats["type"], txn_stats["alerts"], label="Cảnh báo", color="#ef4444", alpha=0.8)
    axes[0, 1].set_title("Giao Dịch Và Cảnh Báo Theo Loại")
    axes[0, 1].tick_params(axis="x", rotation=20)
    axes[0, 1].legend()

    hourly = eval_pd.groupby("hour").agg(fraud=("isfraud", "sum")).reset_index()
    axes[0, 2].bar(hourly["hour"], hourly["fraud"], color="#f59e0b")
    axes[0, 2].set_title("Gian Lận Theo Giờ")
    axes[0, 2].set_xlabel("Giờ")

    axes[1, 0].hist(
        [eval_pd.loc[eval_pd["isfraud"] == 0, "ml_probability"], eval_pd.loc[eval_pd["isfraud"] == 1, "ml_probability"]],
        bins=40,
        color=["#60a5fa", "#ef4444"],
        label=["Bình thường", "Gian lận"],
        alpha=0.7,
        density=True,
    )
    axes[1, 0].axvline(0.5, color="#111827", linestyle="--", linewidth=1.5)
    axes[1, 0].set_title("Phân Bố Xác Suất Máy Học")
    axes[1, 0].legend()

    axes[1, 1].hist(
        [eval_pd.loc[eval_pd["isfraud"] == 0, "composite_score"], eval_pd.loc[eval_pd["isfraud"] == 1, "composite_score"]],
        bins=40,
        color=["#60a5fa", "#ef4444"],
        label=["Bình thường", "Gian lận"],
        alpha=0.7,
        density=True,
    )
    axes[1, 1].axvline(FINAL_THRESHOLD, color="#111827", linestyle="--", linewidth=1.5)
    axes[1, 1].set_title("Phân Bố Điểm Lai")
    axes[1, 1].legend()

    x_index = range(len(metrics_pd))
    axes[1, 2].bar([x - 0.2 for x in x_index], metrics_pd["precision"], width=0.2, label="Precision", color="#0ea5e9")
    axes[1, 2].bar(x_index, metrics_pd["recall"], width=0.2, label="Recall", color="#f97316")
    axes[1, 2].bar([x + 0.2 for x in x_index], metrics_pd["f1"], width=0.2, label="F1", color="#22c55e")
    axes[1, 2].set_xticks(list(x_index), metrics_pd["mo_hinh"])
    axes[1, 2].set_ylim(0, 1.05)
    axes[1, 2].set_title("So Sánh Luật, Máy Học Và Lai")
    axes[1, 2].legend()

    plt.tight_layout()
    plt.savefig((REPORTS_DIR / "dashboard.png").as_posix(), dpi=120, bbox_inches="tight")
    plt.close(fig)

    # File top tài khoản rủi ro cao giúp giải trình tính thực tiễn của hệ thống.
    top_accounts = (
        scored.filter("final_alert = 1")
        .groupBy("nameorig")
        .agg(
            F.count("*").alias("alert_count"),
            F.round(F.sum("amount"), 2).alias("total_amount"),
            F.round(F.avg("composite_score"), 4).alias("avg_score"),
        )
        .orderBy(F.col("alert_count").desc(), F.col("avg_score").desc())
        .limit(20)
        .toPandas()
    )
    top_accounts.to_csv((REPORTS_DIR / "top_risk_accounts.csv").as_posix(), index=False)


def main() -> None:
    # Gold là tầng cuối; chỉ chạy khi đã có model và Silver stream.
    ensure_runtime_dirs()
    if not MODEL_DIR.exists():
        raise FileNotFoundError(f"Không tìm thấy mô hình đã huấn luyện tại {MODEL_DIR}. Hãy chạy train_model trước.")

    spark = get_spark("TangGold")
    model = PipelineModel.load(PATHS["model"])
    # Tạo sẵn Silver rỗng để Gold có thể bật trước khi Silver có batch đầu tiên.
    ensure_delta_table(spark, PATHS["silver"], SILVER_SCHEMA, partition_by="type")

    def write_gold_batch(batch_df, batch_id: int) -> None:
        """Chấm điểm một micro-batch, ghi alerts và cập nhật metrics/dashboard."""
        if batch_df.isEmpty():
            return
        started_at = time.time()
        scored_batch = _score_batch(model, batch_df)
        total_rows = scored_batch.count()
        alert_rows = scored_batch.filter("final_alert = 1").count()

        scored_batch.write.format("delta").mode("append").partitionBy("type").save(PATHS["gold_scored"])
        (
            scored_batch.filter("final_alert = 1")
            .select(
                "txn_id",
                "step",
                "type",
                "amount",
                "nameorig",
                "namedest",
                "rule_blacklist",
                "rule_large_txn",
                "rule_drain",
                "rule_blacklist_burst",
                "rule_score",
                "rule_score_normalized",
                "ml_probability",
                "ml_prediction",
                "composite_score",
                "final_alert",
                "alert_reason",
                F.col("isfraud").alias("true_label"),
                "scored_at",
            )
            .write.format("delta")
            .mode("append")
            .save(PATHS["gold_alerts"])
        )

        # Đọc lại Gold scored để cập nhật báo cáo tổng hợp sau mỗi batch.
        scored_all = spark.read.format("delta").load(PATHS["gold_scored"])
        metrics_df = (
            scored_all.groupBy("type")
            .agg(
                F.count("*").alias("total_txn"),
                F.sum("isfraud").alias("fraud_count"),
                F.sum("final_alert").alias("alert_count"),
                F.round(F.avg("amount"), 2).alias("avg_amount"),
                F.round(F.avg("ml_probability"), 4).alias("avg_ml_probability"),
                F.round(F.avg("composite_score"), 4).alias("avg_composite_score"),
            )
            .withColumn("fraud_rate_pct", F.round(F.col("fraud_count") / F.col("total_txn") * 100, 4))
            .withColumn("alert_rate_pct", F.round(F.col("alert_count") / F.col("total_txn") * 100, 4))
            .withColumn("created_at", F.current_timestamp())
        )
        metrics_df.write.format("delta").mode("overwrite").option("overwriteSchema", "true").save(PATHS["gold_metrics"])

        _render_dashboard(spark)
        elapsed_ms = round((time.time() - started_at) * 1000)
        with (REPORTS_DIR / "latest_gold_batch.json").open("w", encoding="utf-8") as fh:
            json.dump({"ma_lo": batch_id, "so_dong": total_rows, "so_canh_bao": alert_rows, "thoi_gian_ms": elapsed_ms}, fh, indent=2)
        print(f"Lô Gold {batch_id:03d} | dòng={total_rows:,} | cảnh_báo={alert_rows:,} | {elapsed_ms} ms")

    stream_df = spark.readStream.format("delta").load(PATHS["silver"])
    stream_df.explain(mode="simple")
    query = (
        stream_df.writeStream.foreachBatch(write_gold_batch)
        .option("checkpointLocation", PATHS["gold_checkpoint"])
        .trigger(processingTime=GOLD_TRIGGER_INTERVAL)
        .queryName("gold_stream")
        .start()
    )
    print(f"Đã khởi động luồng Gold | id={query.id}")
    query.awaitTermination()


if __name__ == "__main__":
    main()
