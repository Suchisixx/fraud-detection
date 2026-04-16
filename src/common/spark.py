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

"""
Vai trò:
- Khởi tạo SparkSession chuẩn cho toàn dự án.
- Tạo Delta table rỗng khi cần để các stream downstream có thể khởi động trước.

Tiêu chí:
- Hiệu quả xử lý và tối ưu mã nguồn: mọi cấu hình Spark tối ưu local demo được
  gom tại đây, giúp dễ kiểm soát shuffle, bộ nhớ và Delta integration.
- Kiến trúc dữ liệu và khả năng mở rộng: các job dùng cùng một chuẩn SparkSession.
"""


def get_spark(app_name: str = APP_NAME) -> SparkSession:
    """Tạo hoặc tái sử dụng SparkSession cấu hình sẵn cho dự án."""
    global _SPARK
    ensure_runtime_dirs()
    if _SPARK is not None:
        return _SPARK

    builder = (
        SparkSession.builder.appName(app_name)
        .master(SPARK_MASTER)
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
        .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog")
        # Giảm shuffle cho môi trường local để demo mượt hơn.
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
    """
    Tạo Delta table rỗng đúng schema nếu chưa tồn tại.

    Vai trò:
    - Cho phép Silver / Gold stream khởi động trước cả khi Bronze / Silver chưa có batch.
    """
    table_path = Path(path)
    if (table_path / "_delta_log").exists():
        return

    writer = spark.createDataFrame([], schema).write.format("delta").mode("overwrite")
    if partition_by:
        writer = writer.partitionBy(partition_by)
    writer.save(table_path.as_posix())
