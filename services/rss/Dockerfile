FROM python:3.11-slim AS rss

WORKDIR /app

RUN apt-get update && apt-get install -y \
    --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY services/rss/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/rss/ ./ 
COPY services/rss/config.yaml ./config.yaml
EXPOSE 8000

ENV PYTHONUNBUFFERED=1

RUN useradd --create-home --shell /usr/sbin/nologin appuser && chown -R appuser:appuser /app
USER appuser

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
