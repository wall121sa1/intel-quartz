# Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system deps (for spaCy)
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY services/ner/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN python -m spacy download en_core_web_lg

# Copy app code
COPY services/ner/app.py .

# Expose port
EXPOSE 8000

# Start the service
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
