import spacy
from watcher.app.models import ArticleData

# Load the model once
nlp = spacy.load("en_core_web_sm")

def extract_entities(article: ArticleData) -> ArticleData:
    doc = nlp(article.content)
    
    # 1. Extract unique lists for YAML (Keep these clean strings)
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

    article.organizations = list(orgs)
    article.people = list(people)
    article.locations = list(locs)

    # 2. Inject WikiLinks into the Body Text
    # We sort entities by start_char in descending order (Reverse)
    # so that modifying the string doesn't mess up the indices of earlier entities.
    entities_reversed = sorted(doc.ents, key=lambda e: e.start_char, reverse=True)
    
    new_content = article.content

    for ent in entities_reversed:
        # Check if the entity is one we want to link
        if ent.label_ in ["ORG", "PERSON", "GPE", "LOC"]:
            start = ent.start_char
            end = ent.end_char
            
            # Construct the new string with brackets
            # Logic: Text_Before + [[Entity]] + Text_After
            new_content = (
                new_content[:start] 
                + "[[" + new_content[start:end] + "]]" 
                + new_content[end:]
            )
            
    article.content = new_content
    
    return article