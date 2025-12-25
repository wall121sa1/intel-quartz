FROM python:3.9-slim AS harvester

WORKDIR /app

COPY services/harvester/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/harvester/worker.py .

CMD ["python", "-u", "worker.py"]
