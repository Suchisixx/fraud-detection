from __future__ import annotations

import time

from src.common.config import PATHS, SILVER_TRIGGER_INTERVAL, ensure_runtime_dirs
from src.common.features import build_silver_frame
from src.common.rules import apply_rule_engine, empty_blacklist_df, load_blacklist_df
from src.common.schemas import BRONZE_SCHEMA
from src.common.spark import ensure_delta_table, get_spark

"""
Vai trò:
- Tầng Silver: làm sạch dữ liệu, tạo feature engineering và áp dụng rule engine.

Liên hệ tiêu chí:
- Độ chính xác và giá trị thực tiễn: đây là nơi rule-based detection được kích hoạt.
- Hiệu quả xử lý: dùng Delta downstream, chống trùng và giữ logic online đồng nhất với offline.
"""


def main() -> None:
    ensure_runtime_dirs()
    spark = get_spark("TangSilver")
    # Blacklist là dữ liệu tham chiếu; nếu chưa có thì pipeline vẫn chạy để demo.
    blacklist_df = load_blacklist_df(spark)
    if blacklist_df.isEmpty():
        blacklist_df = empty_blacklist_df(spark)
        print("Danh sách đen đang rỗng. Luồng Silver vẫn chạy nhưng luật blacklist sẽ chưa kích hoạt.")
    else:
        print(f"Đã nạp danh sách đen với {blacklist_df.count():,} tài khoản")

    # Tạo sẵn Bronze rỗng để Silver có thể đứng chờ trước khi Bronze có batch đầu tiên.
    ensure_delta_table(spark, PATHS["bronze"], BRONZE_SCHEMA, partition_by="type")
    stream_df = spark.readStream.format("delta").load(PATHS["bronze"])
    build_silver_frame(stream_df).explain(mode="simple")

    def write_silver_batch(batch_df, batch_id: int) -> None:
        """Xử lý một micro-batch Silver và ghi ra Delta Silver."""
        if batch_df.isEmpty():
            return
        started_at = time.time()
        silver_batch = apply_rule_engine(build_silver_frame(batch_df), blacklist_df)
        row_count = silver_batch.count()
        alert_count = silver_batch.filter("rule_alert = 1").count()
        silver_batch.write.format("delta").mode("append").partitionBy("type").save(PATHS["silver"])
        elapsed_ms = round((time.time() - started_at) * 1000)
        print(f"Lô Silver {batch_id:03d} | dòng={row_count:,} | cảnh_báo={alert_count:,} | {elapsed_ms} ms")

    query = (
        stream_df.writeStream.foreachBatch(write_silver_batch)
        .option("checkpointLocation", PATHS["silver_checkpoint"])
        .trigger(processingTime=SILVER_TRIGGER_INTERVAL)
        .queryName("silver_stream")
        .start()
    )
    print(f"Đã khởi động luồng Silver | id={query.id}")
    query.awaitTermination()


if __name__ == "__main__":
    main()
