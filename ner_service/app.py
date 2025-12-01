"""NER service with health checks and hot reload support."""
from __future__ import annotations

import logging
import os
import socket
import time
from threading import Lock
from typing import Any, Dict, List, Optional

import spacy
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field
from spacy.language import Language

app = FastAPI()

SERVICE_NAME = os.getenv("SERVICE_NAME", "ner-service")
INSTANCE_ID = os.getenv("INSTANCE_ID", socket.gethostname())
SPACY_MODEL = os.getenv("SPACY_MODEL", "en_core_web_sm")

START_TIME = time.time()
rules_lock = Lock()
logger = logging.getLogger("ner_service")
logging.basicConfig(level=logging.INFO)


class ProcessRequest(BaseModel):
    text: str


class ReloadRequest(BaseModel):
    rules: Dict[str, Any] = Field(default_factory=dict)
    model: Optional[str] = Field(
        default=None,
        description="Optional SpaCy model name to hot-swap for new tenants/traffic.",
    )
    update_id: Optional[str] = Field(
        default=None,
        description=(
            "Cluster-scoped update identifier; prevents stale reloads when multiple "
            "instances receive the same training/rules payload."
        ),
    )
    training_data_version: Optional[str] = Field(
        default=None,
        description="Version or timestamp of the underlying training data for traceability.",
    )


def load_spacy_model(model_name: str) -> Language:
    """Load a SpaCy model by name, raising HTTPException on failure."""
    try:
        return spacy.load(model_name)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Failed to load model {model_name}: {exc}")


def initialize_state() -> None:
    """Initialize shared state for this FastAPI instance."""
    app.state.model_name = SPACY_MODEL
    app.state.model = load_spacy_model(SPACY_MODEL)
    app.state.custom_rules: Dict[str, Any] = {"tags": []}
    app.state.rules_version = 1
    app.state.ready = True
    app.state.update_id: Optional[str] = None
    app.state.training_data_version: Optional[str] = None


@app.on_event("startup")
def on_startup() -> None:
    initialize_state()


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log inbound requests with caller info for debugging cross-service traffic."""
    caller = request.headers.get("X-Watcher-Client") or request.headers.get("User-Agent")
    client_host = request.client.host if request.client else "unknown"
    start = time.time()
    try:
        response = await call_next(request)
    except Exception as exc:  # noqa: BLE001
        elapsed = round((time.time() - start) * 1000, 2)
        logger.exception(
            "Request failed: path=%s caller=%s client=%s latency_ms=%.2f",
            request.url.path,
            caller,
            client_host,
            elapsed,
        )
        raise

    elapsed = round((time.time() - start) * 1000, 2)
    logger.info(
        "Request completed: path=%s status=%s caller=%s client=%s latency_ms=%.2f",
        request.url.path,
        getattr(response, "status_code", "unknown"),
        caller,
        client_host,
        elapsed,
    )
    return response


@app.get("/health/live")
def liveness() -> Dict[str, Any]:
    """Liveness probe used by load balancers to weed out dead pods."""
    return {
        "status": "alive",
        "service": SERVICE_NAME,
        "instance_id": INSTANCE_ID,
        "uptime_seconds": round(time.time() - START_TIME, 3),
    }


@app.get("/health/ready")
def readiness() -> Dict[str, Any]:
    """Readiness probe confirms the model and rules are available."""
    is_ready = bool(getattr(app.state, "ready", False) and getattr(app.state, "model", None))
    return {
        "status": "ready" if is_ready else "not_ready",
        "service": SERVICE_NAME,
        "instance_id": INSTANCE_ID,
        "model": getattr(app.state, "model_name", None),
        "rules_version": getattr(app.state, "rules_version", 0),
        "update_id": getattr(app.state, "update_id", None),
        "training_data_version": getattr(app.state, "training_data_version", None),
        "uptime_seconds": round(time.time() - START_TIME, 3),
        "ready": is_ready,
    }


@app.get("/health")
def health_root() -> Dict[str, Any]:
    """Backwards-compatible health endpoint; mirrors readiness."""
    return readiness()


@app.post("/process")
def process(req: ProcessRequest, request: Request) -> Dict[str, Any]:
    """
    Main NER endpoint.
    Input: {"text": "..."}
    Output: the JSON shape you described.
    """
    with rules_lock:
        nlp: Language = app.state.model
        rules_snapshot = {"tags": list(app.state.custom_rules.get("tags", []))}

    try:
        doc = nlp(req.text)
    except Exception as exc:  # noqa: BLE001
        caller = request.headers.get("X-Watcher-Client") or request.headers.get("User-Agent")
        logger.exception("NER processing failed for caller=%s", caller)
        raise HTTPException(status_code=500, detail=f"ner_processing_failed: {exc}")

    orgs: List[str] = []
    people: List[str] = []
    locs: List[str] = []
    events: List[str] = []
    tags: List[str] = []

    for ent in doc.ents:
        if ent.label_ in ("ORG",):
            orgs.append(ent.text)
        elif ent.label_ in ("PERSON",):
            people.append(ent.text)
        elif ent.label_ in ("GPE", "LOC"):
            locs.append(ent.text)
        elif ent.label_ in ("EVENT",):
            events.append(ent.text)

    lower_text = req.text.lower()
    for tag in rules_snapshot.get("tags", []):
        if tag.lower() in lower_text:
            tags.append(tag)

    annotated = req.text
    for ent in doc.ents:
        annotated = annotated.replace(ent.text, f"[{ent.text}](#)")

    return {
        "text": req.text,
        "entities": {
            "orgs": sorted(set(orgs)),
            "people": sorted(set(people)),
            "locs": sorted(set(locs)),
            "events": sorted(set(events)),
            "tags": sorted(set(tags)),
        },
        "content_with_links": annotated,
    }


@app.post("/reload")
def reload_rules(req: ReloadRequest) -> Dict[str, Any]:
    """Reload rules and optionally swap SpaCy models without downtime."""
    with rules_lock:
        if req.update_id and getattr(app.state, "update_id", None) == req.update_id:
            return {
                "status": "skipped",
                "reason": "update_already_applied",
                "service": SERVICE_NAME,
                "instance_id": INSTANCE_ID,
                "model": app.state.model_name,
                "rules_version": app.state.rules_version,
                "update_id": app.state.update_id,
                "training_data_version": app.state.training_data_version,
            }

        if req.model and req.model != app.state.model_name:
            app.state.ready = False
            new_model = load_spacy_model(req.model)
            app.state.model = new_model
            app.state.model_name = req.model
            app.state.ready = True

        app.state.custom_rules = req.rules or {}
        app.state.custom_rules.setdefault("tags", [])
        app.state.rules_version += 1
        app.state.update_id = req.update_id or app.state.update_id
        app.state.training_data_version = req.training_data_version or app.state.training_data_version

        return {
            "status": "reloaded",
            "service": SERVICE_NAME,
            "instance_id": INSTANCE_ID,
            "model": app.state.model_name,
            "rules_version": app.state.rules_version,
            "update_id": app.state.update_id,
            "training_data_version": app.state.training_data_version,
            "rules": app.state.custom_rules,
        }
