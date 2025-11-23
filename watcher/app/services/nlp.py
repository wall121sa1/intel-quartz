import spacy
from flask import current_app
from app.models import CustomEntity

# Global variable to hold the loaded model
_nlp_pipeline = None

def get_nlp_pipeline():
    global _nlp_pipeline
    
    if _nlp_pipeline is not None:
        return _nlp_pipeline

    print("NLP: Initializing Pipeline...")
    
    try:
        _nlp_pipeline = spacy.load("en_core_web_sm")
    except OSError:
        print("CRITICAL: Spacy model not found. Run: python -m spacy download en_core_web_sm")
        return None

    # 1. Add EntityRuler (Rule-based matching)
    if "entity_ruler" not in _nlp_pipeline.pipe_names:
        ruler = _nlp_pipeline.add_pipe("entity_ruler", before="ner", config={"overwrite_ents": True})
    else:
        ruler = _nlp_pipeline.get_pipe("entity_ruler")
        ruler.clear_patterns()

    # 2. Fetch rules from Database
    try:
        if current_app:
            with current_app.app_context():
                entities = CustomEntity.query.all()
                patterns = []
                for e in entities:
                    patterns.append({"label": e.label, "pattern": e.text})
                
                # FIX: Only add patterns if list is not empty to avoid Spacy UserWarning [W036]
                if patterns:
                    ruler.add_patterns(patterns)
                    print(f"NLP: Loaded {len(patterns)} custom rules.")
                else:
                    print("NLP: No custom rules found in DB (EntityRuler empty).")
                    
    except Exception as e:
        print(f"NLP Warning: Could not load custom entities. Error: {e}")

    return _nlp_pipeline

class NLPService:
    @staticmethod
    def reload_model():
        """Force reload of model to pick up new DB entries"""
        global _nlp_pipeline
        _nlp_pipeline = None
        get_nlp_pipeline()

    @staticmethod
    def process_text(text):
        nlp = get_nlp_pipeline()
        
        # Default empty structure to prevent KeyError in manager.py
        empty_result = {
            "entities": {
                "orgs": [], "people": [], "locs": [], 
                "events": [], "tags": [] # FIX: Added 'tags' key
            },
            "content_with_links": text
        }

        if not nlp or not text:
            return empty_result

        doc = nlp(text)
        
        # 1. Extract unique entities
        orgs = set()
        people = set()
        locs = set()
        events = set()
        tags = set()

        for ent in doc.ents:
            if ent.label_ == "ORG":
                orgs.add(ent.text)
            elif ent.label_ == "PERSON":
                people.add(ent.text)
            elif ent.label_ in ["GPE", "LOC"]:
                locs.add(ent.text)
            elif ent.label_ in ["EVENT", "DATE"]: 
                if ent.label_ == "EVENT":
                    events.add(ent.text)
            elif ent.label_ in ["TAG", "TOPIC"]: 
                # FIX: Support auto-tagging if user adds rules with 'TAG' label
                tags.add(ent.text)

        # 2. Inject WikiLinks
        entities_reversed = sorted(doc.ents, key=lambda e: e.start_char, reverse=True)
        new_content = text

        for ent in entities_reversed:
            # We treat TAG/TOPIC as metadata, not necessarily wikilinks in text, 
            # but you can add them to this list if you want them linked.
            if ent.label_ in ["ORG", "PERSON", "GPE", "LOC", "EVENT", "TAG", "TOPIC"]:
                start = ent.start_char
                end = ent.end_char
                
                # Check surroundings
                is_wrapped = (start >= 2 and new_content[start-2:start] == "[[")
                
                if not is_wrapped:
                    new_content = (
                        new_content[:start] 
                        + "[[" + new_content[start:end] + "]]" 
                        + new_content[end:]
                    )

        return {
            "entities": {
                "orgs": list(orgs),
                "people": list(people),
                "locs": list(locs),
                "events": list(events),
                "tags": list(tags) # FIX: Return the tags list
            },
            "content_with_links": new_content
        }