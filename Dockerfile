# ==========================================
# STAGE 1: Shared Base for Python Services
# ==========================================
FROM python:3.11-slim AS python-base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# COPY GLOBAL REQUIREMENTS
COPY requirements.txt .
RUN pip install -r requirements.txt

# Download Spacy model globally so all services have it
RUN python -m spacy download en_core_web_lg

# ==========================================
# SERVICE: Watcher
# ==========================================
FROM python-base AS watcher
COPY services/watcher/ .
RUN chmod +x entrypoint.sh
ENV FLASK_APP=run:app
EXPOSE 5000
ENTRYPOINT ["./entrypoint.sh"]
CMD ["gunicorn", "-b", "0.0.0.0:5000", "run:app"]

# ==========================================
# SERVICE: Watcher Worker
# ==========================================
FROM watcher AS watcher-worker
CMD ["python", "worker.py"]

# ==========================================
# SERVICE: NER
# ==========================================
FROM python-base AS ner
COPY services/ner/ .
EXPOSE 8000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]

# ==========================================
# SERVICE: Telegram RSS
# ==========================================
FROM python-base AS rss
COPY services/rss/ .
# Note: config.yaml is usually mounted via volume, but we copy a default here
COPY services/rss/config.yaml ./config.yaml
RUN chmod +x entrypoint.sh
EXPOSE 8000
ENTRYPOINT ["./entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

# ==========================================
# SERVICE: Harvester
# ==========================================
FROM python-base AS harvester
COPY services/harvester/ .
CMD ["python", "-u", "worker.py"]

# ==========================================
# SERVICE: Quartz (Node.js)
# ==========================================
FROM node:22-slim AS quartz
WORKDIR /usr/src/app
RUN npm install -g npm@11.6.4
COPY services/quartz/package.json services/quartz/package-lock.json* ./
COPY services/quartz/scripts/checkNpmVersion.mjs ./scripts/
RUN npm ci
COPY services/quartz/ .
CMD ["bash"]
