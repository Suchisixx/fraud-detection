$ErrorActionPreference = "Stop"

docker compose up -d --build
docker compose exec -d fraud python -m src.jobs.bronze_stream
docker compose exec -d fraud python -m src.jobs.silver_stream
docker compose exec -d fraud python -m src.jobs.gold_stream
docker compose exec fraud python -m src.jobs.simulate_stream
