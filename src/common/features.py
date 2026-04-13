from __future__ import annotations

from itertools import chain

from pyspark.sql import DataFrame, functions as F

from src.common.config import LARGE_TXN_THRESHOLD, TYPE_TO_INDEX

RAW_TO_NORMALIZED = {
    "nameOrig": "nameorig",
    "oldbalanceOrg": "oldbalanceorig",
    "newbalanceOrig": "newbalanceorig",
    "nameDest": "namedest",
    "oldbalanceDest": "oldbalancedest",
    "newbalanceDest": "newbalancedest",
    "isFraud": "isfraud",
    "isFlaggedFraud": "isflaggedfraud",
}

def _build_type_index_map():
    return F.create_map([F.lit(x) for x in chain(*TYPE_TO_INDEX.items())])


def normalize_transaction_columns(df: DataFrame) -> DataFrame:
    normalized = df
    for old_name, new_name in RAW_TO_NORMALIZED.items():
        if old_name in normalized.columns and new_name not in normalized.columns:
            normalized = normalized.withColumnRenamed(old_name, new_name)
    if "txn_id" not in normalized.columns:
        normalized = normalized.withColumn(
            "txn_id",
            F.sha2(
                F.concat_ws(
                    "||",
                    F.coalesce(F.col("step").cast("string"), F.lit("NULL")),
                    F.coalesce(F.col("type"), F.lit("NULL")),
                    F.coalesce(F.col("amount").cast("string"), F.lit("NULL")),
                    F.coalesce(F.col("nameorig"), F.lit("NULL")),
                    F.coalesce(F.col("namedest"), F.lit("NULL")),
                    F.coalesce(F.col("oldbalanceorig").cast("string"), F.lit("NULL")),
                    F.coalesce(F.col("newbalanceorig").cast("string"), F.lit("NULL")),
                    F.coalesce(F.col("oldbalancedest").cast("string"), F.lit("NULL")),
                    F.coalesce(F.col("newbalancedest").cast("string"), F.lit("NULL")),
                ),
                256,
            ),
        )
    return normalized


def clean_transactions(df: DataFrame) -> DataFrame:
    return (
        df.filter(F.col("amount") > 0)
        .filter(F.col("nameorig").isNotNull())
        .filter(F.col("namedest").isNotNull())
        .dropDuplicates(["txn_id"])
    )


def add_feature_columns(df: DataFrame) -> DataFrame:
    type_index_map = _build_type_index_map()
    return (
        df.withColumn("type_upper", F.upper(F.col("type")))
        .withColumn(
            "error_balance_orig",
            F.col("oldbalanceorig") - F.col("amount") - F.col("newbalanceorig"),
        )
        .withColumn(
            "error_balance_dest",
            F.col("newbalancedest") - F.col("oldbalancedest") - F.col("amount"),
        )
        .withColumn(
            "amount_ratio",
            F.col("amount") / (F.coalesce(F.col("oldbalanceorig"), F.lit(0.0)) + F.lit(1.0)),
        )
        .withColumn(
            "is_zero_balance_after",
            F.when((F.col("newbalanceorig") == 0) & (F.col("oldbalanceorig") > 0), 1).otherwise(0),
        )
        .withColumn(
            "is_large_amount",
            F.when(F.col("amount") > LARGE_TXN_THRESHOLD, 1).otherwise(0),
        )
        .withColumn("hour", (F.col("step") % 24).cast("int"))
        .withColumn(
            "type_index",
            F.coalesce(type_index_map[F.col("type_upper")], F.lit(-1.0)).cast("double"),
        )
        .drop("type_upper")
    )


def build_silver_frame(df: DataFrame) -> DataFrame:
    return add_feature_columns(clean_transactions(normalize_transaction_columns(df)))
