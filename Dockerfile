# syntax=docker/dockerfile:1
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    TRACEZERO_MODELS_DIR=/app/models

WORKDIR /app

# System libraries needed by PyMuPDF and Torch CPU wheels
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    libmupdf-dev \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml requirements.txt README.md LICENSE ./
COPY src/ ./src/

RUN pip install --upgrade pip && \
    pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir .

VOLUME ["/app/models"]
EXPOSE 8000

ENTRYPOINT ["tracezero"]
CMD ["serve", "--host", "0.0.0.0", "--port", "8000"]
