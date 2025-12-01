import logging
from datetime import datetime, timedelta

import requests
import spacy
from flask import current_app
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from app.models import CustomEntity

# Initialize logger
logger = logging.getLogger(__name__)

# Global variable
_nlp_pipeline = None
_remote_nlp_url = os.getenv("NER_SERVICE_URL", "http://ner:8000")
_remote_timeout = float(os.getenv("NER_SERVICE_TIMEOUT", "15"))
_remote_failure_threshold = int(os.getenv("NER_SERVICE_FAILURE_THRESHOLD", "3"))
_remote_backoff_seconds = int(os.getenv("NER_SERVICE_BACKOFF_SECONDS", "300"))
_remote_pool_size = int(os.getenv("NER_SERVICE_POOL_SIZE", "10"))

_remote_session = None
_remote_disable_until: datetime | None = None
_remote_failures = 0


def _collect_custom_rules():
    """Return custom entity rules as pattern dicts."""
    try:
        if current_app:
            entities = CustomEntity.query.all()
            return [{"label": e.label, "pattern": e.text} for e in entities]
    except Exception as exc:
        logger.warning("NLP: DB Rule Load Error (Ignore if DB init): %s", exc)

    return []


def load_custom_rules(nlp):
    """Helper to load rules from DB into the provided nlp object"""
    patterns = _collect_custom_rules()
    if not patterns:
        return

    ruler = nlp.get_pipe("entity_ruler")
    ruler.clear_patterns()  # Clear old to avoid duplicates on reload
    ruler.add_patterns(patterns)
    logger.info("NLP: Loaded %s custom rules.", len(patterns))


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
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        _remote_session = session

    return _remote_session


def _remote_available():
    return not _remote_disable_until or datetime.utcnow() >= _remote_disable_until


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


def get_nlp_pipeline():
    global _nlp_pipeline

    if _nlp_pipeline is not None:
        return _nlp_pipeline

    logger.info("NLP: Loading Spacy Model...")
    try:
        # Disable components we don't need to save RAM (e.g., parser if we only need entities)
        # keeping 'ner' is essential. 'parser' is heavy, disable if not doing dependency parsing.
        _nlp_pipeline = spacy.load(
            "en_core_web_sm", disable=['parser', 'tagger', 'attribute_ruler', 'lemmatizer']
        )

        # Add EntityRuler
        if "entity_ruler" not in _nlp_pipeline.pipe_names:
            _nlp_pipeline.add_pipe("entity_ruler", before="ner", config={"overwrite_ents": True})

        # Load rules
        load_custom_rules(_nlp_pipeline)

    except OSError:
        logger.critical("NLP: Model not found. downloading...")
        from spacy.cli import download
        download("en_core_web_sm")
        _nlp_pipeline = spacy.load(
            "en_core_web_sm", disable=['parser', 'tagger', 'attribute_ruler', 'lemmatizer']
        )

    return _nlp_pipeline


class NLPService:
    @staticmethod
    def process_text(text):
        """
        Processes text to extract entities and inject wikilinks.
        """
        global _remote_failures
        empty_result = {
            "entities": {"orgs": [], "people": [], "locs": [], "events": [], "tags": []},
            "content_with_links": text,
        }

        if not text:
            return empty_result

        # Always prefer the remote NER endpoint (default) so models stay centralized.
        if _remote_available():
            try:
                payload = {"text": text}
                custom_rules = _collect_custom_rules()
                if custom_rules:
                    payload["rules"] = custom_rules

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

                logger.warning("NLP: Remote response missing expected keys, falling back to local pipeline")
            except Exception as exc:
                _record_remote_failure(exc)
                logger.warning("NLP: Remote service unavailable, falling back to local pipeline: %s", exc)
        elif _remote_disable_until:
            logger.debug(
                "NLP: Skipping remote NER until %s after repeated failures.", _remote_disable_until.isoformat()
            )

        return NLPService._process_text_local(text, empty_result)

    @staticmethod
    def _process_text_local(text, empty_result):
        nlp = get_nlp_pipeline()

        if not nlp:
            return empty_result

        # Increase max length for large articles (default is 1,000,000)
        nlp.max_length = 2000000

        doc = nlp(text)

        # 1. Extract unique entities using set comprehensions
        orgs = {ent.text for ent in doc.ents if ent.label_ == "ORG"}
        people = {ent.text for ent in doc.ents if ent.label_ == "PERSON"}
        locs = {ent.text for ent in doc.ents if ent.label_ in ["GPE", "LOC"]}
        events = {ent.text for ent in doc.ents if ent.label_ in ["EVENT", "DATE"] if ent.label_ == "EVENT"}  # Strict event check
        tags = {ent.text for ent in doc.ents if ent.label_ in ["TAG", "TOPIC"]}

        # 2. Inject WikiLinks (Reverse order replacement)
        entities_reversed = sorted(doc.ents, key=lambda e: e.start_char, reverse=True)
        new_content = text

        # Optimization: Use a set for faster lookup
        linkable_labels = {"ORG", "PERSON", "GPE", "LOC", "EVENT", "TAG", "TOPIC"}

        for ent in entities_reversed:
            if ent.label_ in linkable_labels:
                start, end = ent.start_char, ent.end_char
                # Check for existing brackets [[...]]
                if start >= 2 and new_content[start-2:start] == "[[":
                    continue

                # Check for markdown links [...] or (...)
                # Simple heuristic: don't break existing markdown links
                if start > 0 and new_content[start-1] == "[":
                    continue

                new_content = f"{new_content[:start]}[[{new_content[start:end]}]]{new_content[end:]}"

        return {
            "entities": {
                "orgs": list(orgs), "people": list(people), "locs": list(locs),
                "events": list(events), "tags": list(tags)
            },
            "content_with_links": new_content
        }

    @staticmethod
    def reload_model():
        """Force refresh of the NLP model and sync any remote service."""
        global _nlp_pipeline
        _nlp_pipeline = None

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
            logger.warning("NLP: Remote reload failed, refreshing local pipeline instead: %s", exc)

        # Fallback to refreshing the in-process pipeline to keep UI dictionary tests working.
        get_nlp_pipeline()
