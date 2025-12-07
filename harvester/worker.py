import os
import time
import json
import frontmatter
import requests
import re
import urllib.parse
from geopy.geocoders import Nominatim
from countryinfo import CountryInfo  # For capital city logic

# --- CONFIGURATION ---
FUSEKI_ENDPOINT = os.getenv("FUSEKI_ENDPOINT", "http://obsidian-secure-backend:3030/knowledge-graph/update")
WATCH_DIR = "/data"  # Inside Docker, we map this to your articles folder
POLL_INTERVAL = 60   # Run every 60 seconds
BASE_URI = "http://myvault.com/"

# Initialize Geocoder (with a custom user agent to be polite)
geolocator = Nominatim(user_agent="obsidian_harvester_v1")

def clean_id(text):
    """Turns 'Elon Musk' into 'Elon_Musk' for URIs"""
    return urllib.parse.quote(text.strip().replace(" ", "_").replace('"', '').replace("'", ""))

def is_url(text):
    """Checks if a location string is actually a URL"""
    # Regex for common URL patterns
    return re.match(r'^(http|https|www\.|ftp|[a-zA-Z0-9-]+\.[a-zA-Z]{2,})', text.strip())

def get_coordinates(location_name):
    """
    Smart Geocoding:
    1. Ignores URLs.
    2. If it's a Country, finds the Capital City first.
    3. Otherwise, geocodes the name directly.
    """
    if is_url(location_name):
        print(f"   🚫 Ignoring URL location: {location_name}")
        return None

    try:
        # Check if it is a country
        country = CountryInfo(location_name)
        try:
            # Try to get info. If it fails, it's likely not a country name in this library
            capital = country.capital()
            print(f"   🌍 Detected Country '{location_name}'. Using capital: {capital}")
            location_name = f"{capital}, {location_name}" # Geocode the capital
        except KeyError:
            # Not a country, treat as normal city/place
            pass
        
        # Geocode
        loc = geolocator.geocode(location_name, timeout=10)
        if loc:
            return (loc.latitude, loc.longitude)
    except Exception as e:
        print(f"   ⚠️ Geocoding error for '{location_name}': {e}")
    
    return None

def process_article(md_path, json_path):
    print(f"📄 Processing: {os.path.basename(md_path)}")
    
    # 1. Read Markdown (Frontmatter)
    with open(md_path, 'r', encoding='utf-8') as f:
        post = frontmatter.load(f)
    
    # 2. Read JSON Sidecar
    entities = {}
    if os.path.exists(json_path):
        with open(json_path, 'r', encoding='utf-8') as f:
            entities = json.load(f)

    # 3. Generate Triples
    triples = []
    slug = os.path.basename(md_path).replace(".md", "")
    article_uri = f"<{BASE_URI}article/{clean_id(slug)}>"
    
    # -- Metadata --
    title = post.metadata.get('title', slug).replace('"', '\\"')
    triples.append(f'{article_uri} <{BASE_URI}prop/title> "{title}" .')
    triples.append(f'{article_uri} <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <{BASE_URI}class/Article> .')

    # -- Entities from JSON --
    # Map JSON keys to RDF Classes
    entity_map = {
        "organizations": "Organization",
        "people": "Person",
        "events": "Event",
        "locations": "Location"
    }

    for category, class_name in entity_map.items():
        if category in entities:
            for item in entities[category]:
                item_clean = item.strip()
                entity_uri = f"<{BASE_URI}entity/{clean_id(item_clean)}>"
                
                # Link Article -> Entity
                triples.append(f'{article_uri} <{BASE_URI}prop/mentions> {entity_uri} .')
                
                # Define Entity Type
                triples.append(f'{entity_uri} <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <{BASE_URI}class/{class_name}> .')
                triples.append(f'{entity_uri} <http://www.w3.org/2000/01/rdf-schema#label> "{item_clean.replace("\"", "")}" .')

                # -- Special Handling for Locations --
                if category == "locations":
                    coords = get_coordinates(item_clean)
                    if coords:
                        lat, lng = coords
                        triples.append(f'{entity_uri} <{BASE_URI}prop/lat> "{lat}" .')
                        triples.append(f'{entity_uri} <{BASE_URI}prop/lng> "{lng}" .')

    # 4. Push to Fuseki
    if triples:
        update_query = f"""
        DELETE {{ {article_uri} ?p ?o }} WHERE {{ {article_uri} ?p ?o }};
        INSERT DATA {{ {' '.join(triples)} }}
        """
        try:
            r = requests.post(FUSEKI_ENDPOINT, data={'update': update_query})
            if r.status_code in [200, 204]:
                print("   ✅ Synced to Graph")
            else:
                print(f"   ❌ Fuseki Error: {r.text}")
        except Exception as e:
            print(f"   ❌ Connection Error: {e}")

def main():
    print("🚀 Harvester started. Watching for .md + .json pairs...")
    while True:
        # Simple scan - in production, we might verify 'last modified' timestamps
        for filename in os.listdir(WATCH_DIR):
            if filename.endswith(".md"):
                md_path = os.path.join(WATCH_DIR, filename)
                json_path = os.path.join(WATCH_DIR, filename.replace(".md", ".entities.json"))
                
                # Only process if BOTH exist (or at least MD exists)
                process_article(md_path, json_path)
        
        print(f"💤 Sleeping {POLL_INTERVAL}s...")
        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    main()