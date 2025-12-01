# app.py
from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Dict, Any
import spacy

app = FastAPI()

# Load SpaCy model once at startup (this is the “heavy” part)
nlp = spacy.load("en_core_web_sm")

# Simple in-memory rules store (for /reload)
# You can extend this later.
custom_rules = {
    "tags": []  # e.g. ["crypto", "bitcoin", ...]
}

class ProcessRequest(BaseModel):
    text: str

class ReloadRequest(BaseModel):
    rules: Dict[str, Any]


@app.get("/health")
def health():
    """Simple health check endpoint."""
    return {"status": "ok"}


@app.post("/process")
def process(req: ProcessRequest):
    """
    Main NER endpoint.
    Input: {"text": "..."}
    Output: the JSON shape you described.
    """
    text = req.text
    doc = nlp(text)

    orgs: List[str] = []
    people: List[str] = []
    locs: List[str] = []
    events: List[str] = []
    tags: List[str] = []

    # Basic entity extraction with SpaCy
    for ent in doc.ents:
        if ent.label_ in ("ORG",):
            orgs.append(ent.text)
        elif ent.label_ in ("PERSON",):
            people.append(ent.text)
        elif ent.label_ in ("GPE", "LOC"):
            locs.append(ent.text)
        elif ent.label_ in ("EVENT",):
            events.append(ent.text)

    # Very simple tag logic using our custom_rules["tags"]
    lower_text = text.lower()
    for t in custom_rules.get("tags", []):
        if t.lower() in lower_text:
            tags.append(t)

    # Build a very basic "annotated markdown"
    # For now we just wrap entities in []()
    # In your real system you’d replace with wiki links.
    annotated = text
    for ent in doc.ents:
        # naive replace, good enough for starting
        annotated = annotated.replace(ent.text, f"[{ent.text}](#)")

    return {
        "text": text,
        "entities": {
            "orgs": list(set(orgs)),
            "people": list(set(people)),
            "locs": list(set(locs)),
            "events": list(set(events)),
            "tags": list(set(tags)),
        },
        "content_with_links": annotated,
    }


@app.post("/reload")
def reload_rules(req: ReloadRequest):
    """
    Replace in-memory rules with what the client sends.
    Example payload:
    {
      "rules": {
        "tags": ["crypto", "bitcoin", "ethereum"]
      }
    }
    """
    global custom_rules
    custom_rules = req.rules or {}
    # Make sure "tags" is always present
    custom_rules.setdefault("tags", [])
    return {"status": "reloaded", "rules": custom_rules}
