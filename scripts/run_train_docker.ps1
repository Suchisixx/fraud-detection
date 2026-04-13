$ErrorActionPreference = "Stop"

docker compose up -d --build
docker compose exec fraud python -m src.jobs.seed_blacklist
docker compose exec fraud python -m src.jobs.train_model
