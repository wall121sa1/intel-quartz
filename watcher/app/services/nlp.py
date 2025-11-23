import spacy
from flask import current_app
from app.models import CustomEntity

# Global variable to hold the loaded model
_nlp_pipeline = None

def get_nlp_pipeline():
    global _nlp_pipeline
    
    # If pipeline exists, return it. 
    # To force reload, the caller must set _nlp_pipeline = None
    if _nlp_pipeline is not None:
        return _nlp_pipeline

    print("NLP: Initializing Pipeline...")
    
    # 1. Load the base model
    try:
        # Disable 'ner' temporarily to add ruler before it, or load full and insert
        _nlp_pipeline = spacy.load("en_core_web_sm")
    except OSError:
        print("CRITICAL: Spacy model not found. Run: python -m spacy download en_core_web_sm")
        return None

    # 2. Add EntityRuler (Rule-based matching)
    # We verify if it exists to avoid duplicates on weird reloads
    if "entity_ruler" not in _nlp_pipeline.pipe_names:
        # 'before="ner"' ensures our rules run first and claim the tokens
        ruler = _nlp_pipeline.add_pipe("entity_ruler", before="ner", config={"overwrite_ents": True})
    else:
        ruler = _nlp_pipeline.get_pipe("entity_ruler")
        ruler.clear_patterns() # Clear old patterns if reloading

    # 3. Fetch rules from Database
    try:
        # We access the DB directly. 
        # This works because this function is always called inside a Flask Request Context
        entities = CustomEntity.query.all()
        
        patterns = []
        for e in entities:
            # Create a pattern that is case-insensitive (optional, removes strictness)
            # For exact match only, use: {"label": e.label, "pattern": e.text}
            patterns.append({"label": e.label, "pattern": e.text})
            
        ruler.add_patterns(patterns)
        print(f"NLP: Loaded {len(patterns)} custom rules. Examples: {[p['pattern'] for p in patterns[:3]]}")
        
    except Exception as e:
        print(f"NLP Warning: Could not load custom entities from DB. Error: {e}")

    return _nlp_pipeline

class NLPService:
    @staticmethod
    def reload_model():
        """Force reload of model to pick up new DB entries"""
        print("NLP: Requesting Model Reload...")
        global _nlp_pipeline
        _nlp_pipeline = None
        # Initialize immediately to catch errors early
        get_nlp_pipeline()

    @staticmethod
    def process_text(text):
        nlp = get_nlp_pipeline()
        if not nlp or not text:
            return {
                "entities": {"orgs": [], "people": [], "locs": [], "events": [], "tags": []},
                "content_with_links": text
            }

        doc = nlp(text)
        
        # 1. Extract unique entities
        orgs = set()
        people = set()
        locs = set()
        events = set()

        for ent in doc.ents:
            if ent.label_ == "ORG":
                orgs.add(ent.text)
            elif ent.label_ == "PERSON":
                people.add(ent.text)
            elif ent.label_ in ["GPE", "LOC"]:
                locs.add(ent.text)
            elif ent.label_ in ["EVENT", "DATE"]: 
                # We map 'DATE' to event if it was caught by our custom ruler
                # But primarily we want explicit 'EVENT' labels from our ruler
                if ent.label_ == "EVENT":
                    events.add(ent.text)
            
            # Debug print for development
            # print(f"Entity Found: {ent.text} ({ent.label_})")

        # 2. Inject WikiLinks (Reverse order strategy)
        entities_reversed = sorted(doc.ents, key=lambda e: e.start_char, reverse=True)
        new_content = text

        for ent in entities_reversed:
            if ent.label_ in ["ORG", "PERSON", "GPE", "LOC", "EVENT"]:
                start = ent.start_char
                end = ent.end_char
                
                # Check surroundings to prevent [[[[Double Brackets]]]]
                # We look 2 chars back and 2 chars forward (safely)
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
                "events": list(events)
            },
            "content_with_links": new_content
        }