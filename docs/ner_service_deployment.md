# NER Service Deployment Guide

This guide describes how to build, configure, and operate the NER service in scalable environments (containers, Kubernetes, and behind load balancers). It summarizes runtime expectations from `ner_service/app.py` and the shipping Docker assets.

## Overview
- **Service name**: configurable via `SERVICE_NAME` (default: `ner-service`).
- **Instance identifier**: configurable via `INSTANCE_ID` (defaults to container hostname) to distinguish replicas in logs and health checks.
- **Model**: SpaCy model name via `SPACY_MODEL` (default: `en_core_web_sm`).
- **Ports**: HTTP API exposed on port `8000` by default (see Dockerfile and Uvicorn command).
- **Health probes**:
  - `GET /health/live`: liveness for load balancers / orchestrators.
  - `GET /health/ready` (alias `/health`): readiness that returns model, rules version, `update_id`, and `training_data_version` to confirm synchronized updates across replicas.
- **Reload endpoint**: `POST /reload` accepts new rules, optional SpaCy model name, and optional `update_id`/`training_data_version` to coordinate cluster-wide updates and avoid reapplying stale payloads.

## Prerequisites
- Docker 20.10+ (or compatible runtime such as containerd).
- Python 3.11-slim base image with build tooling for SpaCy (handled inside the Dockerfile).
- Network access to download SpaCy models during image build (default downloads `en_core_web_sm`).

## Building the container image
```bash
cd ner_service
# Build with default model
docker build -t ner-service:latest .

# Override the SpaCy model at build time by passing a build-arg and updating the Dockerfile
# or post-start via the reload endpoint (see Runtime configuration).
```

The provided `ner_service/Dockerfile` installs system dependencies, installs Python requirements, downloads the default SpaCy model, copies `app.py`, exposes port 8000, and starts Uvicorn (`uvicorn app:app --host 0.0.0.0 --port 8000`).

## Running locally with Docker Compose
```bash
cd ner_service
docker-compose up --build
# Service available at http://localhost:8000
```

The sample `docker-compose.yml` maps host port 8000 to the container and restarts unless stopped. Adjust the port or environment variables as needed for local testing.

## Runtime configuration
Set the following environment variables at container runtime (via Compose, Kubernetes, or your orchestrator):
- `SERVICE_NAME`: logical service name surfaced in health responses (default: `ner-service`).
- `INSTANCE_ID`: unique identifier per replica; defaults to the container hostname.
- `SPACY_MODEL`: SpaCy model to load on startup; can be hot-swapped later via `/reload`.

Example Docker run:
```bash
docker run -d \
  -p 8000:8000 \
  -e SERVICE_NAME=ner-service \
  -e INSTANCE_ID=ner-01 \
  -e SPACY_MODEL=en_core_web_sm \
  ner-service:latest
```

## Health checks for load balancers
Configure your load balancer or orchestrator to use the exposed probes:
- **Liveness**: `GET /health/live` — returns `status: "alive"` plus `service`, `instance_id`, and `uptime_seconds`. Use for restart policies to detect dead pods/containers.
- **Readiness**: `GET /health/ready` — returns `status`, `ready` boolean, model name, `rules_version`, `update_id`, and `training_data_version`. Use to keep only up-to-date instances in rotation; the service sets `ready` to `False` briefly during model swaps.

## Coordinated reloads across replicas
Use the reload endpoint to push synchronized updates (rules and/or models) to all instances behind a load balancer:
```bash
curl -X POST http://ner.example.com/reload \
  -H "Content-Type: application/json" \
  -d '{
    "rules": {"tags": ["Intel", "AI"]},
    "model": "en_core_web_sm",
    "update_id": "2024-05-12T10:00Z-r1",
    "training_data_version": "trainset-v42"
  }'
```
- `update_id`: a cluster-scoped identifier for the reload payload. If an instance already applied the same `update_id`, it returns `status: "skipped"` to avoid reapplying stale updates.
- `training_data_version`: surfaced in readiness to signal the training data backing the current rules/model.
- The service sets `ready=False` during model swaps to avoid serving traffic mid-update; readiness flips back to `True` once the new model is loaded and rules are applied.

## Scaling behind a load balancer
1. Run multiple replicas (Docker Compose `scale`/`replicas` or Kubernetes Deployments/ReplicaSets).
2. Point the load balancer to each replica on port 8000.
3. Configure health checks using `/health/live` (liveness) and `/health/ready` (readiness) so that only synchronized, ready instances receive traffic.
4. When rolling out new rules or models, send the reload payload (with `update_id` and `training_data_version`) to all replicas. Instances that already applied the update will respond with `status: "skipped"`; others will reload and become ready once updates finish.

## Example Kubernetes manifest (Deployment + Service)
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ner-service
spec:
  replicas: 3
  selector:
    matchLabels:
      app: ner-service
  template:
    metadata:
      labels:
        app: ner-service
    spec:
      containers:
        - name: ner
          image: ner-service:latest
          ports:
            - containerPort: 8000
          env:
            - name: SERVICE_NAME
              value: ner-service
            - name: SPACY_MODEL
              value: en_core_web_sm
          readinessProbe:
            httpGet:
              path: /health/ready
              port: 8000
            initialDelaySeconds: 5
            periodSeconds: 10
          livenessProbe:
            httpGet:
              path: /health/live
              port: 8000
            initialDelaySeconds: 5
            periodSeconds: 10
---
apiVersion: v1
kind: Service
metadata:
  name: ner-service
spec:
  selector:
    app: ner-service
  ports:
    - port: 80
      targetPort: 8000
      protocol: TCP
  type: ClusterIP
```

## Observability and operations
- **Tracing updates**: Use `update_id` and `training_data_version` from `/health/ready` responses to confirm all replicas are synchronized.
- **Concurrency safety**: Reloads and request handling are guarded by a threading lock around rules/model access to avoid race conditions during hot reload.
- **Uptime**: `/health/live` includes uptime in seconds; useful for debugging restarts.

## Security considerations
- Place the service behind an authenticated gateway if reloads should be restricted; by default, endpoints are unauthenticated.
- If exposing `/reload`, ensure only trusted automation can call it (e.g., via network ACLs, mTLS, or an API gateway auth policy).

## Failure handling
- Model load failures during `/reload` return HTTP 500 and keep the previous model/rules intact; readiness remains `False` until a model is successfully loaded.
- If a reload is skipped due to matching `update_id`, the instance keeps serving traffic with its current model/rules.

## Data persistence
- The service keeps state in memory only (model object, custom rules, versions). Use an external controller to orchestrate reloads across replicas when new training data or tagging rules are published.
