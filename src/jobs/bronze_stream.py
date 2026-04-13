from __future__ import annotations

import time

from pyspark.sql import functions as F

from src.common.config import (
    BRONZE_TRIGGER_INTERVAL,
    PATHS,
    STREAM_MAX_FILES_PER_TRIGGER,
    ensure_runtime_dirs,
)
from src.common.features import normalize_transaction_columns
from src.common.schemas import PAYSIM_SCHEMA
from src.common.spark import get_spark


def _write_bronze_batch(batch_df, batch_id: int) -> None:
    if batch_df.isEmpty():
        return
    started_at = time.time()
    row_count = batch_df.count()
    fraud_count = batch_df.filter("isfraud = 1").count()
    batch_df.write.format("delta").mode("append").partitionBy("type").save(PATHS["bronze"])
    elapsed_ms = round((time.time() - started_at) * 1000)
    print(f"Lô Bronze {batch_id:03d} | dòng={row_count:,} | gian_lận={fraud_count:,} | {elapsed_ms} ms")


def main() -> None:
    ensure_runtime_dirs()
    spark = get_spark("TangBronze")

    raw_stream = (
        spark.readStream.format("csv")
        .option("header", "true")
        .option("maxFilesPerTrigger", str(STREAM_MAX_FILES_PER_TRIGGER))
        .option("recursiveFileLookup", "true")
        .schema(PAYSIM_SCHEMA)
        .load(PATHS["stream_input"])
    )

    bronze_df = (
        normalize_transaction_columns(raw_stream)
        .withColumn("ingested_at", F.current_timestamp())
        .withColumn("source_file", F.input_file_name())
    )

    bronze_df.explain(mode="simple")
    query = (
        bronze_df.writeStream.foreachBatch(_write_bronze_batch)
        .option("checkpointLocation", PATHS["bronze_checkpoint"])
        .trigger(processingTime=BRONZE_TRIGGER_INTERVAL)
        .queryName("bronze_stream")
        .start()
    )
    print(f"Đã khởi động luồng Bronze | id={query.id}")
    query.awaitTermination()


if __name__ == "__main__":
    main()
