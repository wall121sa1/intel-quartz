# NER service architecture for memory resilience

The local SpaCy pipeline works for small loads, but for many concurrent feeds it consumes a lot of RAM. To keep the watcher workers stable in production, run the named-entity-recognition (NER) logic as a separate service and call it over HTTP.

## Recommended topology

- **Dedicated NER container**: Package SpaCy (or a lighter model) behind a small FastAPI/Flask server that exposes `/process` accepting `{ "text": "..." }`.
- **Horizontal scaling**: Run multiple replicas of the NER container behind a load balancer so Celery workers never hold the model in memory.
- **Isolated resources**: Give the NER container a higher memory limit and a warmup probe so the model loads before traffic starts.
- **Backpressure**: Use Celery prefetch limits (`worker_prefetch_multiplier=1`) and `max_tasks_per_child` to keep the watcher worker memory flat even during bursts.
- **Circuit breaker**: If the remote NER times out, the watcher falls back to the in-process SpaCy model so articles still get processed.

## How to enable the remote service

1. Deploy the NER API and expose a base URL (e.g., `http://ner:8000`).
2. The watcher defaults to `http://ner:8000` but you can override it with `NER_SERVICE_URL`. The application always `POST`s to `<NER_SERVICE_URL>/process` and will only fall back to the local model if the service is unreachable.
   - Control networking behavior with:
     - `NER_SERVICE_TIMEOUT` (seconds) to bound slow responses.
     - `NER_SERVICE_FAILURE_THRESHOLD` and `NER_SERVICE_BACKOFF_SECONDS` to temporarily pause remote calls after repeated errors (avoids blocking the worker while the service restarts).
     - `NER_SERVICE_POOL_SIZE` to size the HTTP connection pool when multiple feeds are processed concurrently.
   - The watcher identifies itself to the remote service using the `X-Watcher-Client` header (defaults to the container hostname, override with `NER_SERVICE_CLIENT_ID`). This makes it easy to filter incoming logs or traces per caller.
3. Keep the endpoint contract:
   ```json
   {
     "text": "input text",
     "entities": {
       "orgs": ["..."],
       "people": ["..."],
       "locs": ["..."],
       "events": ["..."],
       "tags": ["..."]
     },
     "content_with_links": "annotated markdown"
   }
   ```
4. Monitor latency; if the service becomes slow the watcher will log a warning and automatically fall back to the local model.
5. Expose a `/reload` endpoint that accepts `{"rules": [...]}` so dictionary changes (add/delete/import/feedback learning) can refresh the remote model without restarting it.

## Operational knobs

- **Worker size**: Keep Celery worker concurrency low (e.g., 1–2) when using the local model; with the remote service you can raise concurrency because the heavy model lives elsewhere.
- **Task chunking**: Continue committing/expunging each article inside tasks to avoid growing the SQLAlchemy identity map.
- **Health checks**: Add a `/health` endpoint to the NER service and wire it into orchestration so unhealthy pods are rotated out quickly.

This setup limits the memory footprint of the watcher workers while keeping NLP results available even if the remote service is temporarily unreachable.
