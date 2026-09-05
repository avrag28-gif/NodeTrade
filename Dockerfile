FROM python:3.12-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

COPY requirements.txt pyproject.toml ./
RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src
COPY dashboard ./dashboard
COPY models ./models

CMD ["sh", "-c", "uvicorn nodetrade.server:app --host 0.0.0.0 --port ${PORT:-8000}"]
