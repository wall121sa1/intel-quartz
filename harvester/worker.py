import os
import time
import json
import frontmatter
import requests
import re
import urllib.parse
from geopy.geocoders import Nominatim
from countryinfo import CountryInfo

# --- CONFIGURATION ---
# We read these from Docker environment variables
FUSEKI_ENDPOINT = os.getenv("FUSEKI_ENDPOINT", "http://localhost:3030/knowledge-graph/update")
WATCH_DIR = os.getenv("WATCH_DIR", "/data")
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "60"))
BASE_URI = "http://myvault.com/"

geolocator = Nominatim(user_agent="obsidian_harvester_v2")

def clean_id(text):
    return urllib.parse.quote(text.strip().replace(" ", "_").replace('"', '').replace("'", ""))

def is_url(text):
    return re.match(r'^(http|https|www\.|ftp|[a-zA-Z0-9-]+\.[a-zA-Z]{2,})', text.strip())

def get_coordinates(location_name):
    if is_url(location_name): return None
    try:
        # Try Country Capital Logic
        try:
            country = CountryInfo(location_name)
            capital = country.capital()
            if capital: location_name = f"{capital}, {location_name}"
        except: pass
        
        loc = geolocator.geocode(location_name, timeout=10)
        if loc: return (loc.latitude, loc.longitude)
    except: pass
    return None

def process_article(md_path, json_path):
    # Check if we have processed this recently to avoid spamming Fuseki (Optional optimization)
    # For now, we just process.
    
    with open(md_path, 'r', encoding='utf-8') as f:
        try: post = frontmatter.load(f)
        except: return # Skip bad files

    entities = {}
    if os.path.exists(json_path):
        with open(json_path, 'r', encoding='utf-8') as f:
            try: entities = json.load(f)
            except: pass

    # --- RDF Generation (Same as before) ---
    triples = []
    slug = os.path.basename(md_path).replace(".md", "")
    article_uri = f"<{BASE_URI}article/{clean_id(slug)}>"
    
    title = post.metadata.get('title', slug).replace('"', '\\"')
    triples.append(f'{article_uri} <{BASE_URI}prop/title> "{title}" .')
    triples.append(f'{article_uri} <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <{BASE_URI}class/Article> .')

    entity_map = {"organizations": "Organization", "people": "Person", "locations": "Location"}
    
    for category, class_name in entity_map.items():
        if category in entities:
            for item in entities[category]:
                item = item.strip()
                entity_uri = f"<{BASE_URI}entity/{clean_id(item)}>"
                triples.append(f'{article_uri} <{BASE_URI}prop/mentions> {entity_uri} .')
                triples.append(f'{entity_uri} <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <{BASE_URI}class/{class_name}> .')
                triples.append(f'{entity_uri} <http://www.w3.org/2000/01/rdf-schema#label> "{item.replace("\"", "")}" .')

                if category == "locations":
                    coords = get_coordinates(item)
                    if coords:
                        triples.append(f'{entity_uri} <{BASE_URI}prop/lat> "{coords[0]}" .')
                        triples.append(f'{entity_uri} <{BASE_URI}prop/lng> "{coords[1]}" .')

    if triples:
        update_query = f"DELETE {{ {article_uri} ?p ?o }} WHERE {{ {article_uri} ?p ?o }}; INSERT DATA {{ {' '.join(triples)} }}"
        try:
            requests.post(FUSEKI_ENDPOINT, data={'update': update_query})
            print(f"✅ Synced: {slug}")
        except Exception as e:
            print(f"❌ Error syncing {slug}: {e}")

def main():
    print(f"🚀 Harvester running. Watching {WATCH_DIR} recursively...")
    while True:
        # Recursive Scan
        for root, dirs, files in os.walk(WATCH_DIR):
            for filename in files:
                if filename.endswith(".md"):
                    md_path = os.path.join(root, filename)
                    # Look for sidecar in same folder
                    json_path = os.path.join(root, filename.replace(".md", ".entities.json"))
                    process_article(md_path, json_path)
        
        print(f"💤 Sleeping {POLL_INTERVAL}s...")
        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    main()