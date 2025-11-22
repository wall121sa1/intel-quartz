import spacy

# Load model globally to avoid reloading it on every request
try:
    nlp_engine = spacy.load("en_core_web_sm")
except OSError:
    # Fallback or instruction if model isn't found
    print("Spacy model 'en_core_web_sm' not found. Run: python -m spacy download en_core_web_sm")
    nlp_engine = None

class NLPService:
    @staticmethod
    def process_text(text):
        """
        Returns a dictionary with:
        - entities: dict of lists (orgs, people, locs)
        - content_with_links: str (text with [[Links]] injected)
        """
        if not nlp_engine or not text:
            return {
                "entities": {"orgs": [], "people": [], "locs": []},
                "content_with_links": text
            }

        doc = nlp_engine(text)
        
        # 1. Extract unique entities for metadata
        orgs = set()
        people = set()
        locs = set()

        for ent in doc.ents:
            if ent.label_ == "ORG":
                orgs.add(ent.text)
            elif ent.label_ == "PERSON":
                people.add(ent.text)
            elif ent.label_ in ["GPE", "LOC"]:
                locs.add(ent.text)

        # 2. Inject WikiLinks into the body text (Reverse order strategy)
        # We process in reverse so inserting characters doesn't shift indices of earlier entities
        entities_reversed = sorted(doc.ents, key=lambda e: e.start_char, reverse=True)
        new_content = text

        for ent in entities_reversed:
            if ent.label_ in ["ORG", "PERSON", "GPE", "LOC"]:
                start = ent.start_char
                end = ent.end_char
                
                # Wrap in brackets: ... text [[Entity]] text ...
                new_content = (
                    new_content[:start] 
                    + "[[" + new_content[start:end] + "]]" 
                    + new_content[end:]
                )

        return {
            "entities": {
                "orgs": list(orgs),
                "people": list(people),
                "locs": list(locs)
            },
            "content_with_links": new_content
        }