# Vai trò:
# - Script chạy nhanh cho phần offline: dựng container, seed blacklist, train model.
# - Phù hợp dùng trước giờ demo để chuẩn bị sẵn model và file báo cáo.
$ErrorActionPreference = "Stop"

docker compose up -d --build
docker compose exec fraud python -m src.jobs.seed_blacklist
docker compose exec fraud python -m src.jobs.train_model
