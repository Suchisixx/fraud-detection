from __future__ import annotations

import os
import shutil
import time

from src.common.config import (
    PATHS,
    PAYSIM_CSV,
    SIMULATOR_BATCH_SIZE,
    SIMULATOR_BATCHES,
    SIMULATOR_FRAUD_RATIO,
    SIMULATOR_SLEEP_SECONDS,
    STREAM_INPUT_DIR,
    ensure_runtime_dirs,
)
from src.common.schemas import PAYSIM_SCHEMA
from src.common.spark import get_spark


def main() -> None:
    ensure_runtime_dirs()
    spark = get_spark("FraudSimulator")

    if not PAYSIM_CSV.exists():
        raise FileNotFoundError(f"Không tìm thấy paysim.csv tại {PAYSIM_CSV}")

    full_df = (
        spark.read.format("csv")
        .option("header", "true")
        .schema(PAYSIM_SCHEMA)
        .load(PATHS["raw_csv"])
    )
    total_rows = full_df.count()
    fraud_rows = full_df.filter("isFraud = 1").count()
    print(f"Đã nạp {total_rows:,} dòng | gian_lận={fraud_rows:,} ({fraud_rows / total_rows * 100:.2f}%)")

    if STREAM_INPUT_DIR.exists():
        shutil.rmtree(STREAM_INPUT_DIR)
    STREAM_INPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Đã làm sạch thư mục nhận luồng tại {STREAM_INPUT_DIR}")

    batch_size = int(os.getenv("SIMULATOR_BATCH_SIZE", SIMULATOR_BATCH_SIZE))
    batch_count = int(os.getenv("SIMULATOR_BATCHES", SIMULATOR_BATCHES))
    sleep_seconds = float(os.getenv("SIMULATOR_SLEEP_SECONDS", SIMULATOR_SLEEP_SECONDS))
    fraud_ratio = float(os.getenv("SIMULATOR_FRAUD_RATIO", SIMULATOR_FRAUD_RATIO))

    fraud_pool = full_df.filter("isFraud = 1").cache()
    normal_pool = full_df.filter("isFraud = 0").cache()
    fraud_per_batch = max(1, int(batch_size * fraud_ratio))
    normal_per_batch = batch_size - fraud_per_batch

    print(
        f"Sẽ phát {batch_count} lô x {batch_size} dòng | "
        f"{fraud_per_batch} gian lận + {normal_per_batch} bình thường mỗi lô"
    )

    fraud_pool_count = fraud_pool.count()
    normal_pool_count = normal_pool.count()
    for batch_id in range(batch_count):
        fraud_fraction = min(fraud_per_batch / max(fraud_pool_count, 1) * 3, 1.0)
        normal_fraction = min(normal_per_batch / max(normal_pool_count, 1) * 3, 1.0)
        batch_df = (
            fraud_pool.sample(False, fraud_fraction, seed=batch_id * 11).limit(fraud_per_batch)
            .union(normal_pool.sample(False, normal_fraction, seed=batch_id * 17).limit(normal_per_batch))
            .coalesce(1)
        )

        output_dir = STREAM_INPUT_DIR / f"batch_{batch_id:04d}"
        batch_df.write.mode("overwrite").option("header", "true").csv(output_dir.as_posix())
        print(f"[{batch_id + 1:02d}/{batch_count:02d}] đã ghi {batch_df.count():,} dòng -> {output_dir}")
        if batch_id < batch_count - 1:
            time.sleep(sleep_seconds)

    fraud_pool.unpersist()
    normal_pool.unpersist()
    print("Đã hoàn tất giả lập luồng dữ liệu.")


if __name__ == "__main__":
    main()
