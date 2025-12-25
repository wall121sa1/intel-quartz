# NER service architecture for memory resilience

The local SpaCy pipeline works for small loads, but for many concurrent feeds it consumes a lot of RAM. To keep the watcher workers stable in production, run the named-entity-recognition (NER) logic as a separate service and call it over HTTP. The watcher now requires the remote service; if it is unreachable or not configured, text will be returned unprocessed and a log message will note the failure.

## Recommended topology

- **Dedicated NER container**: Package SpaCy (or a lighter model) behind a small FastAPI/Flask server that exposes `/process` accepting `{ "text": "..." }`.
- **Horizontal scaling**: Run multiple replicas of the NER container behind a load balancer so Celery workers never hold the model in memory.
- **Isolated resources**: Give the NER container a higher memory limit and a warmup probe so the model loads before traffic starts.
- **Backpressure**: Use Celery prefetch limits (`worker_prefetch_multiplier=1`) and `max_tasks_per_child` to keep the watcher worker memory flat even during bursts.
- **Circuit breaker**: If the remote NER times out or cannot be reached, the watcher skips processing for that item and logs the failure.

## How to enable the remote service

1. Deploy the NER API and expose a base URL (e.g., `http://ner:8000`).
2. Set `NER_SERVICE_URL` to point at the service. The application always `POST`s to `<NER_SERVICE_URL>/process` and will skip NLP if the service is unreachable.
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
4. Monitor latency; if the service becomes slow the watcher will log a warning and return unprocessed content.
5. Expose a `/reload` endpoint that accepts `{"rules": [...]}` so dictionary changes (add/delete/import/feedback learning) can refresh the remote model without restarting it.

## Operational knobs

- **Worker size**: The heavy model lives in the remote service, so watcher workers can be tuned without accounting for the model’s memory footprint.
- **Task chunking**: Continue committing/expunging each article inside tasks to avoid growing the SQLAlchemy identity map.
- **Bulk reprocess throttling**: Control how the background NER reprocess loop walks the article table by setting ``NER_REPROCESS_BATCH_SIZE`` (default ``50``) and ``NER_REPROCESS_BATCH_PAUSE_SECONDS`` (default ``0``). Use a small pause (e.g., ``0.25`` seconds) to leave headroom on busy hosts.
- **Health checks**: Add a `/health` endpoint to the NER service and wire it into orchestration so unhealthy pods are rotated out quickly.

This setup limits the memory footprint of the watcher workers while keeping NLP results centralized. If the remote service cannot be reached, processing is skipped and a log entry is emitted.
