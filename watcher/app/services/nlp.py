import spacy
from flask import current_app
from app.models import CustomEntity
import logging

# Initialize logger
logger = logging.getLogger(__name__)

# Global variable
_nlp_pipeline = None

def load_custom_rules(nlp):
    """Helper to load rules from DB into the provided nlp object"""
    try:
        # We need an app context to query the DB
        if current_app:
            entities = CustomEntity.query.all()
            if not entities:
                return

            ruler = nlp.get_pipe("entity_ruler")
            ruler.clear_patterns() # Clear old to avoid duplicates on reload
            
            patterns = [{"label": e.label, "pattern": e.text} for e in entities]
            ruler.add_patterns(patterns)
            logger.info(f"NLP: Loaded {len(patterns)} custom rules.")
    except Exception as e:
        logger.warning(f"NLP: DB Rule Load Error (Ignore if DB init): {e}")

def get_nlp_pipeline():
    global _nlp_pipeline
    
    if _nlp_pipeline is not None:
        return _nlp_pipeline

    logger.info("NLP: Loading Spacy Model...")
    try:
        # Disable components we don't need to save RAM (e.g., parser if we only need entities)
        # keeping 'ner' is essential. 'parser' is heavy, disable if not doing dependency parsing.
        _nlp_pipeline = spacy.load("en_core_web_sm", disable=['parser', 'tagger', 'attribute_ruler', 'lemmatizer'])
        
        # Add EntityRuler
        if "entity_ruler" not in _nlp_pipeline.pipe_names:
            _nlp_pipeline.add_pipe("entity_ruler", before="ner", config={"overwrite_ents": True})
        
        # Load rules
        load_custom_rules(_nlp_pipeline)

    except OSError:
        logger.critical("NLP: Model not found. downloading...")
        from spacy.cli import download
        download("en_core_web_sm")
        _nlp_pipeline = spacy.load("en_core_web_sm", disable=['parser', 'tagger', 'attribute_ruler', 'lemmatizer'])

    return _nlp_pipeline

class NLPService:
    @staticmethod
    def process_text(text):
        """
        Processes text to extract entities and inject wikilinks.
        """
        nlp = get_nlp_pipeline()
        
        empty_result = {
            "entities": {"orgs": [], "people": [], "locs": [], "events": [], "tags": []},
            "content_with_links": text
        }

        if not nlp or not text:
            return empty_result

        # Increase max length for large articles (default is 1,000,000)
        nlp.max_length = 2000000 

        doc = nlp(text)
        
        # 1. Extract unique entities using set comprehensions
        orgs = {ent.text for ent in doc.ents if ent.label_ == "ORG"}
        people = {ent.text for ent in doc.ents if ent.label_ == "PERSON"}
        locs = {ent.text for ent in doc.ents if ent.label_ in ["GPE", "LOC"]}
        events = {ent.text for ent in doc.ents if ent.label_ in ["EVENT", "DATE"] if ent.label_ == "EVENT"} # Strict event check
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