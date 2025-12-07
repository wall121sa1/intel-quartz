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
# Keep the dataset name aligned with the default Fuseki endpoint so initial sync can create it automatically.
FUSEKI_DATASET_NAME = os.getenv("FUSEKI_DATASET_NAME", "knowledge-graph").strip()
FUSEKI_ENDPOINT = os.getenv(
    "FUSEKI_ENDPOINT", f"http://localhost:3030/{FUSEKI_DATASET_NAME}/update"
)
FUSEKI_ADMIN_USER = os.getenv("FUSEKI_ADMIN_USER", "admin")
FUSEKI_ADMIN_PASSWORD = os.getenv("FUSEKI_ADMIN_PASSWORD")
FUSEKI_USER = os.getenv("FUSEKI_USER")
FUSEKI_PASSWORD = os.getenv("FUSEKI_PASSWORD")
WATCH_DIR = os.getenv("WATCH_DIR", "/data")
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "60"))
BASE_URI = os.getenv("BASE_URI", "http://myvault.com/")
if not BASE_URI.endswith("/"):
    BASE_URI = f"{BASE_URI}/"

geolocator = Nominatim(user_agent="obsidian_harvester_v2")

def clean_id(text):
    return urllib.parse.quote(text.strip().replace(" ", "_").replace('"', '').replace("'", ""))

def is_url(text):
    return re.match(r'^(http|https|www\.|ftp|[a-zA-Z0-9-]+\.[a-zA-Z]{2,})', text.strip())

def get_coordinates(location_name):
    if is_url(location_name):
        return None
    try:
        # Try Country Capital Logic
        try:
            country = CountryInfo(location_name)
            capital = country.capital()
            if capital:
                location_name = f"{capital}, {location_name}"
        except Exception:
            pass

        loc = geolocator.geocode(location_name, timeout=10)
        if loc:
            return (loc.latitude, loc.longitude)
    except Exception:
        pass
    return None


def extract_dataset_name(endpoint_url):
    parsed = urllib.parse.urlparse(endpoint_url)
    parts = [p for p in parsed.path.split("/") if p]
    if not parts:
        return None

    # Endpoints are typically /<dataset>/update or /<dataset>/query.
    if parts[-1] in {"update", "query", "data"} and len(parts) >= 2:
        return parts[-2]
    return parts[-1]


def resolve_dataset_name():
    explicit_name = FUSEKI_DATASET_NAME.strip()
    inferred_name = extract_dataset_name(FUSEKI_ENDPOINT)

    if inferred_name and inferred_name != explicit_name:
        print(
            f"FUSEKI_ENDPOINT points to dataset '{inferred_name}', but FUSEKI_DATASET_NAME is set to '{explicit_name}'. Using '{explicit_name}'."
        )

    return explicit_name or inferred_name


def fuseki_update_auth():
    if FUSEKI_PASSWORD and (FUSEKI_USER or FUSEKI_ADMIN_USER):
        return (FUSEKI_USER or FUSEKI_ADMIN_USER, FUSEKI_PASSWORD)
    if FUSEKI_ADMIN_PASSWORD:
        return (FUSEKI_ADMIN_USER, FUSEKI_ADMIN_PASSWORD)
    return None


def fuseki_auth_description():
    if FUSEKI_PASSWORD and (FUSEKI_USER or FUSEKI_ADMIN_USER):
        return f"basic auth as '{FUSEKI_USER or FUSEKI_ADMIN_USER}' with FUSEKI_PASSWORD set"
    if FUSEKI_ADMIN_PASSWORD:
        return f"basic auth as admin '{FUSEKI_ADMIN_USER}' with FUSEKI_ADMIN_PASSWORD set"
    return "no authentication configured"


def fuseki_update_urls():
    urls = [FUSEKI_ENDPOINT]

    try:
        parsed = urllib.parse.urlparse(FUSEKI_ENDPOINT)
        path_parts = [p for p in parsed.path.split("/") if p]

        if path_parts and path_parts[-1] in {"update", "query", "sparql", "data"}:
            path_parts = path_parts[:-1]

        if path_parts:
            dataset_path = "/" + "/".join(path_parts)
            base_dataset_url = f"{parsed.scheme}://{parsed.netloc}{dataset_path}"

            for suffix in ["/update", "?update", "/sparql"]:
                candidate = f"{base_dataset_url}{suffix}"
                if candidate not in urls:
                    urls.append(candidate)
    except Exception:
        pass

    return urls


def ensure_fuseki_dataset():
    dataset_name = resolve_dataset_name()
    parsed = urllib.parse.urlparse(FUSEKI_ENDPOINT)
    fuseki_base = f"{parsed.scheme}://{parsed.netloc}"

    if not dataset_name:
        print("⚠️ Unable to infer dataset name from FUSEKI_ENDPOINT; skipping dataset creation check.")
        return

    dataset_url = f"{fuseki_base}/$/datasets/{dataset_name}"
    auth = None
    if FUSEKI_ADMIN_PASSWORD:
        auth = (FUSEKI_ADMIN_USER, FUSEKI_ADMIN_PASSWORD)

    try:
        response = requests.get(dataset_url, auth=auth, timeout=10)
        if response.status_code == 200:
            try:
                metadata = response.json()
                ds_type = metadata.get("ds.type") or metadata.get("dbType")
                if ds_type and ds_type.lower() != "tdb2":
                    print(
                        f"Dataset '{dataset_name}' exists but is type '{ds_type}', expected 'tdb2' for persistence."
                    )
                return
            except ValueError:
                # Non-JSON response; assume dataset exists but cannot confirm type.
                return
        if response.status_code not in {401, 403, 404}:
            print(f"Unexpected status checking dataset '{dataset_name}': {response.status_code}")
        if response.status_code in {401, 403}:
            print("Fuseki admin credentials are missing or invalid; cannot create dataset automatically.")
            return
    except Exception as e:
        print(f"⚠️ Failed to query Fuseki datasets: {e}")
        return

    try:
        create_response = requests.post(
            f"{fuseki_base}/$/datasets",
            data={"dbName": dataset_name, "dbType": "tdb2"},
            auth=auth,
            timeout=15,
        )
        create_response.raise_for_status()
        print(f"Created Fuseki TDB2 dataset '{dataset_name}'")
    except Exception as e:
        error_detail = ""
        if 'create_response' in locals() and create_response is not None:
            error_detail = f" (status: {create_response.status_code}, body: {create_response.text[:200]})"
        print(f"Unable to create Fuseki dataset '{dataset_name}': {e}{error_detail}")

def process_article(md_path, json_path):
    # Check if we have processed this recently to avoid spamming Fuseki (Optional optimization)
    # For now, we just process.

    with open(md_path, 'r', encoding='utf-8') as f:
        try:
            post = frontmatter.load(f)
        except Exception:
            return  # Skip bad files

    entities = {}
    if os.path.exists(json_path):
        with open(json_path, 'r', encoding='utf-8') as f:
            try:
                entities = json.load(f)
            except Exception:
                pass

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
                sanitized_item = item.replace('"', '')
                entity_uri = f"<{BASE_URI}entity/{clean_id(item)}>"
                triples.append(f'{article_uri} <{BASE_URI}prop/mentions> {entity_uri} .')
                triples.append(
                    f'{entity_uri} <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <{BASE_URI}class/{class_name}> .'
                )
                triples.append(f'{entity_uri} <http://www.w3.org/2000/01/rdf-schema#label> "{sanitized_item}" .')

                if category == "locations":
                    coords = get_coordinates(item)
                    if coords:
                        triples.append(f'{entity_uri} <{BASE_URI}prop/lat> "{coords[0]}" .')
                        triples.append(f'{entity_uri} <{BASE_URI}prop/lng> "{coords[1]}" .')

    if triples:
        update_query = f"DELETE {{ {article_uri} ?p ?o }} WHERE {{ {article_uri} ?p ?o }}; INSERT DATA {{ {' '.join(triples)} }}"
        attempts = []
        auth = fuseki_update_auth()
        for url in fuseki_update_urls():
            response = None
            try:
                response = requests.post(
                    url,
                    data={'update': update_query},
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                    auth=auth,
                    timeout=15,
                )
                response.raise_for_status()
                print(f"✅ Synced: {slug} via {url}")
                break
            except Exception as e:
                status = response.status_code if response is not None else None
                body = response.text[:200] if response is not None else ""
                attempts.append((url, status, f"{e} (body: {body})"))
        else:
            auth_hint = ""
            if any(status in {401, 403} for _, status, _ in attempts):
                auth_hint = " Verify that FUSEKI_* credentials match the users configured in Fuseki's shiro.ini and that the dataset accepts updates."

            attempt_details = "; ".join(
                [f"{url} -> {status or 'error'}: {detail}" for url, status, detail in attempts]
            )
            print(f"❌ Error syncing {slug}: {attempt_details}{auth_hint}")

def main():
    dataset_name = resolve_dataset_name()
    print(f"Targeting Fuseki dataset '{dataset_name}' at {FUSEKI_ENDPOINT}")
    print(f"Fuseki auth mode: {fuseki_auth_description()}")

    ensure_fuseki_dataset()
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
