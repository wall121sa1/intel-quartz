import logging
import os
import socket
from datetime import datetime, timedelta

import requests
from flask import current_app
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from app.models import CustomEntity

# Initialize logger
logger = logging.getLogger(__name__)

def _load_remote_config():
    """Read remote NER configuration from the environment."""

    return {
        # A configured URL is mandatory; empty values will disable processing.
        "url": os.getenv("NER_SERVICE_URL", "").strip(),
        "timeout": float(os.getenv("NER_SERVICE_TIMEOUT", "15")),
        "failure_threshold": int(os.getenv("NER_SERVICE_FAILURE_THRESHOLD", "3")),
        "backoff_seconds": int(os.getenv("NER_SERVICE_BACKOFF_SECONDS", "300")),
        "pool_size": int(os.getenv("NER_SERVICE_POOL_SIZE", "10")),
        "client_id": os.getenv("NER_SERVICE_CLIENT_ID", socket.gethostname()),
    }


_remote_config = _load_remote_config()
_remote_nlp_url = _remote_config["url"]
_remote_timeout = _remote_config["timeout"]
_remote_failure_threshold = _remote_config["failure_threshold"]
_remote_backoff_seconds = _remote_config["backoff_seconds"]
_remote_pool_size = _remote_config["pool_size"]
_remote_client_id = _remote_config["client_id"]

_remote_session = None
_remote_disable_until: datetime | None = None
_remote_failures = 0
_remote_usage_announced = False


def _collect_custom_rules():
    """Return custom entity rules as pattern dicts."""
    try:
        if current_app:
            entities = CustomEntity.query.all()
            return [{"label": e.label, "pattern": e.text} for e in entities]
    except Exception as exc:
        logger.warning("NLP: DB Rule Load Error (Ignore if DB init): %s", exc)

    return []


def _get_remote_session():
    """Return a pooled HTTP session with retries for the NER service."""
    global _remote_session

    if _remote_session is None:
        adapter = HTTPAdapter(
            pool_connections=_remote_pool_size,
            pool_maxsize=_remote_pool_size,
            max_retries=Retry(
                total=2,
                backoff_factor=0.5,
                status_forcelist=[502, 503, 504],
                allowed_methods={"POST"},
                raise_on_status=False,
            ),
        )

        session = requests.Session()
        session.headers.update(
            {
                "User-Agent": f"watcher-ner-client/{_remote_client_id}",
                "X-Watcher-Client": _remote_client_id,
            }
        )
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        _remote_session = session

    return _remote_session


def _remote_available():
    return bool(_remote_nlp_url) and (
        not _remote_disable_until or datetime.utcnow() >= _remote_disable_until
    )


def _record_remote_failure(exc: Exception):
    """Track remote failures and temporarily pause remote calls on repeated errors."""
    global _remote_failures, _remote_disable_until

    _remote_failures += 1
    if _remote_failures >= _remote_failure_threshold:
        _remote_disable_until = datetime.utcnow() + timedelta(seconds=_remote_backoff_seconds)
        _remote_failures = 0
        logger.warning(
            "NLP: Remote service unhealthy; pausing requests for %s seconds (%s)",
            _remote_backoff_seconds,
            exc,
        )


class NLPService:
    @staticmethod
    def process_text(text):
        """
        Processes text to extract entities and inject wikilinks.
        """
        global _remote_failures, _remote_usage_announced
        empty_result = {
            "entities": {"orgs": [], "people": [], "locs": [], "events": [], "tags": []},
            "content_with_links": text,
        }

        if not text:
            return empty_result

        if not _remote_nlp_url:
            message = "NLP: Remote NER service URL is not configured; skipping processing."
            logger.error(message)
            print(message)
            return empty_result

        # Always prefer the remote NER endpoint (default) so models stay centralized.
        if _remote_available():
            try:
                payload = {"text": text}
                custom_rules = _collect_custom_rules()
                if custom_rules:
                    payload["rules"] = custom_rules

                if not _remote_usage_announced:
                    _remote_usage_announced = True
                    message = f"NLP: Using remote NER service at {_remote_nlp_url}"
                    logger.info(message)
                    print(message)

                response = _get_remote_session().post(
                    _remote_nlp_url.rstrip("/") + "/process",
                    json=payload,
                    timeout=_remote_timeout,
                )
                response.raise_for_status()
                data = response.json()
                _remote_failures = 0
                if "content_with_links" in data and "entities" in data:
                    return data

                message = "NLP: Remote response missing expected keys; returning unprocessed content"
                logger.error(message)
                print(message)
            except Exception as exc:
                _record_remote_failure(exc)
                message = f"NLP: Remote service unavailable; returning unprocessed content: {exc}"
                logger.error(message)
                print(message)
        elif _remote_disable_until:
            logger.debug(
                "NLP: Skipping remote NER until %s after repeated failures.", _remote_disable_until.isoformat()
            )

        return empty_result

    @staticmethod
    def reload_model():
        """Force refresh of the NLP model and sync any remote service."""
        if not _remote_nlp_url:
            message = "NLP: Remote NER service URL is not configured; cannot reload model."
            logger.error(message)
            print(message)
            return

        try:
            rules = _collect_custom_rules()
            response = requests.post(
                _remote_nlp_url.rstrip("/") + "/reload",
                json={"rules": rules},
                timeout=10,
            )
            response.raise_for_status()
            logger.info("NLP: Remote model reloaded with %s rules", len(rules))
            return
        except Exception as exc:
            message = f"NLP: Remote reload failed; model remains unchanged: {exc}"
            logger.error(message)
            print(message)
