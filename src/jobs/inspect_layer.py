from src.common.spark import get_spark
from src.common.config import PATHS

spark = get_spark("InspectLayers")

for layer in ["bronze", "silver"]:
    print(f"\n=== {layer.upper()} ===")
    df = spark.read.format("delta").load(PATHS[layer])
    print("count =", df.count())
    df.printSchema()
    df.show(10, truncate=False)
