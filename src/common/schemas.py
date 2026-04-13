from pyspark.sql.types import DoubleType, IntegerType, StringType, StructField, StructType, TimestampType

"""
Vai trò:
- Khai báo schema gốc và schema theo từng tầng dữ liệu.

Liên hệ tiêu chí:
- Kiến trúc dữ liệu: schema rõ ràng giúp giải thích dữ liệu qua Bronze / Silver.
- Hiệu quả xử lý: khai báo schema tường minh giúp Spark đọc ổn định hơn infer schema.
"""


PAYSIM_SCHEMA = StructType(
    [
        StructField("step", IntegerType(), True),
        StructField("type", StringType(), True),
        StructField("amount", DoubleType(), True),
        StructField("nameOrig", StringType(), True),
        StructField("oldbalanceOrg", DoubleType(), True),
        StructField("newbalanceOrig", DoubleType(), True),
        StructField("nameDest", StringType(), True),
        StructField("oldbalanceDest", DoubleType(), True),
        StructField("newbalanceDest", DoubleType(), True),
        StructField("isFraud", IntegerType(), True),
        StructField("isFlaggedFraud", IntegerType(), True),
    ]
)

BLACKLIST_SCHEMA = StructType(
    [
        StructField("account_id", StringType(), True),
        StructField("reason", StringType(), True),
        StructField("added_at", TimestampType(), True),
    ]
)

BRONZE_SCHEMA = StructType(
    [
        StructField("step", IntegerType(), True),
        StructField("type", StringType(), True),
        StructField("amount", DoubleType(), True),
        StructField("nameorig", StringType(), True),
        StructField("oldbalanceorig", DoubleType(), True),
        StructField("newbalanceorig", DoubleType(), True),
        StructField("namedest", StringType(), True),
        StructField("oldbalancedest", DoubleType(), True),
        StructField("newbalancedest", DoubleType(), True),
        StructField("isfraud", IntegerType(), True),
        StructField("isflaggedfraud", IntegerType(), True),
        StructField("txn_id", StringType(), True),
        StructField("ingested_at", TimestampType(), True),
        StructField("source_file", StringType(), True),
    ]
)

SILVER_SCHEMA = StructType(
    BRONZE_SCHEMA.fields
    + [
        StructField("error_balance_orig", DoubleType(), True),
        StructField("error_balance_dest", DoubleType(), True),
        StructField("amount_ratio", DoubleType(), True),
        StructField("is_zero_balance_after", IntegerType(), True),
        StructField("is_large_amount", IntegerType(), True),
        StructField("hour", IntegerType(), True),
        StructField("type_index", DoubleType(), True),
        StructField("rule_blacklist", IntegerType(), True),
        StructField("rule_large_txn", IntegerType(), True),
        StructField("rule_drain", IntegerType(), True),
        StructField("rule_blacklist_burst", IntegerType(), True),
        StructField("rule_score", IntegerType(), True),
        StructField("rule_score_normalized", DoubleType(), True),
        StructField("rule_alert", IntegerType(), True),
    ]
)
