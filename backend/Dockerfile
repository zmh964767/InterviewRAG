FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# System deps: curl for healthcheck; gcc/g++/python3-dev for pypdf2/chromadb/sentence-transformers 编译;
# libgomp1 为 numpy/scikit-learn 运行时需要
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gcc \
    g++ \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 先 COPY requirements 单独一层,代码改动不重装依赖
# 用 PyTorch CPU-only 版本（Docker 容器无 GPU），镜像从 ~10GB 降到 ~3GB
COPY requirements.txt .
RUN pip install --no-cache-dir --default-timeout=300 \
    --extra-index-url https://download.pytorch.org/whl/cpu \
    -r requirements.txt \
    && rm -rf /root/.cache/pip

COPY app/ ./app/

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8080/api/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
