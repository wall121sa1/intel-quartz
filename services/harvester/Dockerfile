FROM python:3.9-slim AS harvester

WORKDIR /app

COPY services/harvester/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/harvester/worker.py .

RUN useradd --create-home --shell /usr/sbin/nologin appuser && chown -R appuser:appuser /app
USER appuser

CMD ["python", "-u", "worker.py"]
