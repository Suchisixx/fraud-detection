from __future__ import annotations

import json

import matplotlib.pyplot as plt
from pyspark.ml import Pipeline
from pyspark.ml.classification import RandomForestClassifier
from pyspark.ml.evaluation import BinaryClassificationEvaluator
from pyspark.ml.feature import StandardScaler, VectorAssembler
from pyspark.ml.functions import vector_to_array
from pyspark.sql import functions as F
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_curve,
    auc as sk_auc,
)

from src.common.config import (
    FEATURE_COLUMNS,
    MODEL_DIR,
    PATHS,
    REPORTS_DIR,
    SUPPORTED_MODEL_TYPES,
    TRAIN_NEGATIVE_RATIO,
    delta_table_exists,
    ensure_runtime_dirs,
)
from src.common.features import build_silver_frame
from src.common.rules import apply_rule_engine, load_blacklist_df
from src.common.schemas import PAYSIM_SCHEMA
from src.common.spark import get_spark


def _load_training_frame(spark):
    if delta_table_exists(MODEL_DIR.parent / "silver"):
        silver = spark.read.format("delta").load(PATHS["silver"])
        if not silver.isEmpty():
            print("Nguồn huấn luyện: bảng Delta Silver hiện có")
            return silver

    print("Nguồn huấn luyện: dữ liệu PaySim gốc kết hợp pipeline tạo đặc trưng dùng chung")
    raw_df = (
        spark.read.format("csv")
        .option("header", "true")
        .schema(PAYSIM_SCHEMA)
        .load(PATHS["raw_csv"])
    )
    silver = build_silver_frame(raw_df)
    blacklist_df = load_blacklist_df(spark)
    return apply_rule_engine(silver, blacklist_df)


def main() -> None:
    ensure_runtime_dirs()
    spark = get_spark("HuanLuyenMoHinhGianLan")

    silver = _load_training_frame(spark)
    pool = silver.filter(F.upper(F.col("type")).isin(*SUPPORTED_MODEL_TYPES))
    fraud_df = pool.filter("isfraud = 1")
    normal_df = pool.filter("isfraud = 0")

    fraud_count = fraud_df.count()
    normal_count = normal_df.count()
    if fraud_count == 0 or normal_count == 0:
        raise RuntimeError("Dữ liệu huấn luyện đang rỗng ở một trong hai lớp: gian lận hoặc bình thường.")

    sample_fraction = min((fraud_count * TRAIN_NEGATIVE_RATIO) / normal_count, 1.0)
    balanced_df = fraud_df.union(normal_df.sample(False, sample_fraction, seed=42))
    train_df, test_df = balanced_df.randomSplit([0.8, 0.2], seed=42)

    assembler = VectorAssembler(inputCols=FEATURE_COLUMNS, outputCol="features_raw", handleInvalid="skip")
    scaler = StandardScaler(inputCol="features_raw", outputCol="features", withMean=True, withStd=True)
    rf = RandomForestClassifier(
        labelCol="isfraud",
        featuresCol="features",
        numTrees=120,
        maxDepth=10,
        featureSubsetStrategy="sqrt",
        seed=42,
    )
    pipeline = Pipeline(stages=[assembler, scaler, rf])

    model = pipeline.fit(train_df)
    predictions = model.transform(test_df)

    binary_eval = BinaryClassificationEvaluator(labelCol="isfraud")
    auc_roc = binary_eval.evaluate(predictions, {binary_eval.metricName: "areaUnderROC"})
    auc_pr = binary_eval.evaluate(predictions, {binary_eval.metricName: "areaUnderPR"})

    scored_pd = (
        predictions.withColumn("ml_probability", vector_to_array(F.col("probability"))[1])
        .select("isfraud", "prediction", "ml_probability")
        .toPandas()
    )
    y_true = scored_pd["isfraud"]
    y_pred = scored_pd["prediction"]
    y_score = scored_pd["ml_probability"]

    metrics = {
        "auc_roc": round(float(auc_roc), 4),
        "auc_pr": round(float(auc_pr), 4),
        "do_chinh_xac": round(float(accuracy_score(y_true, y_pred)), 4),
        "precision": round(float(precision_score(y_true, y_pred, zero_division=0)), 4),
        "recall": round(float(recall_score(y_true, y_pred, zero_division=0)), 4),
        "f1": round(float(f1_score(y_true, y_pred, zero_division=0)), 4),
        "so_dong_gian_lan_huan_luyen": int(fraud_count),
        "so_dong_binh_thuong_huan_luyen": int(normal_count),
        "ti_le_lay_mau_am": round(float(sample_fraction), 4),
    }
    model.write().overwrite().save(PATHS["model"])

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    with (REPORTS_DIR / "training_metrics.json").open("w", encoding="utf-8") as fh:
        json.dump(metrics, fh, indent=2)

    fpr, tpr, _ = roc_curve(y_true, y_score)
    precision_curve, recall_curve, _ = precision_recall_curve(y_true, y_score)
    cm = confusion_matrix(y_true, y_pred)

    fig, axes = plt.subplots(1, 3, figsize=(15, 4))
    axes[0].plot(fpr, tpr, color="#c2410c", lw=2, label=f"AUC={sk_auc(fpr, tpr):.4f}")
    axes[0].plot([0, 1], [0, 1], "--", color="#64748b", lw=1)
    axes[0].set_title("Đường Cong ROC")
    axes[0].set_xlabel("Tỷ Lệ Dương Tính Giả")
    axes[0].set_ylabel("Tỷ Lệ Dương Tính Thật")
    axes[0].legend()
    axes[0].grid(alpha=0.25)

    axes[1].plot(
        recall_curve,
        precision_curve,
        color="#0f766e",
        lw=2,
        label=f"AUC-PR={sk_auc(recall_curve, precision_curve):.4f}",
    )
    axes[1].set_title("Đường Cong Precision-Recall")
    axes[1].set_xlabel("Recall")
    axes[1].set_ylabel("Precision")
    axes[1].legend()
    axes[1].grid(alpha=0.25)

    axes[2].imshow(cm, cmap="Blues")
    axes[2].set_title("Ma Trận Nhầm Lẫn")
    axes[2].set_xticks([0, 1], ["Dự đoán 0", "Dự đoán 1"])
    axes[2].set_yticks([0, 1], ["Thực tế 0", "Thực tế 1"])
    for row in range(cm.shape[0]):
        for col in range(cm.shape[1]):
            axes[2].text(col, row, int(cm[row, col]), ha="center", va="center", color="#111827")

    plt.tight_layout()
    plt.savefig((REPORTS_DIR / "training_curves.png").as_posix(), dpi=120, bbox_inches="tight")
    plt.close(fig)

    print("Đã huấn luyện mô hình xong.")
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
