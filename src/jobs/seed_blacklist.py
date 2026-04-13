from __future__ import annotations

from src.common.config import BLACKLIST_DIR, BLACKLIST_SEED_CSV, PATHS, ensure_runtime_dirs
from src.common.rules import bootstrap_blacklist_reference, load_blacklist_df, persist_blacklist_reference
from src.common.spark import get_spark


def main() -> None:
    ensure_runtime_dirs()
    spark = get_spark("KhoiTaoDanhSachDen")

    blacklist_df = load_blacklist_df(spark)
    if blacklist_df.isEmpty():
        print("Chưa có dữ liệu seed blacklist. Hệ thống sẽ khởi tạo từ các tài khoản gian lận đã biết trong PaySim.")
        blacklist_df = bootstrap_blacklist_reference(spark)
        persist_blacklist_reference(blacklist_df, BLACKLIST_SEED_CSV)
    else:
        print(f"Đã nạp dữ liệu tham chiếu blacklist từ {BLACKLIST_SEED_CSV}")

    (
        blacklist_df.write.format("delta")
        .mode("overwrite")
        .option("overwriteSchema", "true")
        .save(PATHS["blacklist"])
    )
    print(f"Danh sách đen đã sẵn sàng với {blacklist_df.count():,} tài khoản tại {BLACKLIST_DIR}")


if __name__ == "__main__":
    main()
