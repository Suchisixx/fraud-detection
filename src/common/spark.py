from __future__ import annotations

from pathlib import Path

from delta import configure_spark_with_delta_pip
from pyspark.sql import SparkSession
from pyspark.sql.types import StructType

from src.common.config import (
    APP_NAME,
    SPARK_DRIVER_MEMORY,
    SPARK_MASTER,
    SPARK_OFFHEAP_SIZE,
    SPARK_SHUFFLE_PARTITIONS,
    ensure_runtime_dirs,
)

_SPARK: SparkSession | None = None


def get_spark(app_name: str = APP_NAME) -> SparkSession:
    global _SPARK
    ensure_runtime_dirs()
    if _SPARK is not None:
        return _SPARK

    builder = (
        SparkSession.builder.appName(app_name)
        .master(SPARK_MASTER)
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
        .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog")
        .config("spark.sql.shuffle.partitions", SPARK_SHUFFLE_PARTITIONS)
        .config("spark.sql.adaptive.enabled", "true")
        .config("spark.sql.adaptive.coalescePartitions.enabled", "true")
        .config("spark.driver.memory", SPARK_DRIVER_MEMORY)
        .config("spark.memory.offHeap.enabled", "true")
        .config("spark.memory.offHeap.size", SPARK_OFFHEAP_SIZE)
        .config("spark.ui.enabled", "false")
        .config("spark.sql.parquet.filterPushdown", "true")
        .config("spark.databricks.delta.optimizeWrite.enabled", "true")
    )
    _SPARK = configure_spark_with_delta_pip(builder).getOrCreate()
    _SPARK.sparkContext.setLogLevel("ERROR")
    return _SPARK


def ensure_delta_table(
    spark: SparkSession,
    path: str | Path,
    schema: StructType,
    partition_by: str | None = None,
) -> None:
    table_path = Path(path)
    if (table_path / "_delta_log").exists():
        return

    writer = spark.createDataFrame([], schema).write.format("delta").mode("overwrite")
    if partition_by:
        writer = writer.partitionBy(partition_by)
    writer.save(table_path.as_posix())
