# Vai trò:
# - Môi trường chạy chuẩn cho toàn bộ đồ án.
# - Đóng gói Python + Java để Spark và Delta Lake hoạt động ổn định trong Docker.
#
# Liên hệ tiêu chí:
# - Kiến trúc dữ liệu và khả năng mở rộng: giúp dự án chạy nhất quán giữa các máy.
# - Hình thức báo cáo và giải trình: thuận tiện demo vì môi trường được chuẩn hóa.
FROM python:3.11-slim

# Cài Java và các thư viện hệ thống cần thiết cho Spark / scikit-learn.
RUN apt-get update && apt-get install -y --no-install-recommends \
    openjdk-21-jre-headless \
    build-essential \
    gcc \
    g++ \
    libgomp1 \
    ca-certificates \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

ENV JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64
ENV PYSPARK_PYTHON=python3
ENV PYSPARK_DRIVER_PYTHON=python3
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/workspace
ENV WORKSPACE_ROOT=/workspace

# Cài dependency Python của dự án.
COPY requirements.txt /tmp/requirements.txt
RUN python -m pip install --no-cache-dir --upgrade pip setuptools wheel \
    && python -m pip install --no-cache-dir -r /tmp/requirements.txt \
    && rm /tmp/requirements.txt

WORKDIR /workspace

# Giữ container sống để người dùng `docker compose exec` từng job theo nhu cầu.
CMD ["sleep", "infinity"]
