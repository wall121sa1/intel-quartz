import frontmatter
import glob
import requests
import urllib.parse
import os
import re

# ================= CONFIGURATION =================
# 1. Get your Tailscale IP from your server (run `tailscale ip -4` on the server)
TAILSCALE_IP = "100.x.y.z" 
PORT = "3030"
DATASET = "knowledge-graph"

# The secure URL accessible only via your private Tailscale network
FUSEKI_ENDPOINT = f"http://{TAILSCALE_IP}:{PORT}/{DATASET}/update"

# Path to your Obsidian/Quartz content
# (Assuming this script is in /scripts and content is in /content)
VAULT_PATH = "../content/**/*.md" 

# Base URI for your data (doesn't need to be a real website, just unique)
BASE_URI = "http://myvault.com/"
# =================================================

def clean_id(text):
    """Turns 'Elon Musk' into 'Elon_Musk' for valid URIs"""
    # Remove special chars, spaces to underscores
    text = text.replace(" ", "_").replace("'", "").replace('"', "")
    return urllib.parse.quote(text)

def escape_literal(text):
    """Escapes quotes for SPARQL"""
    if not text: return ""
    return str(text).replace('"', '\\"').replace('\n', ' ')

def sync_file(filepath):
    triples = []
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            post = frontmatter.load(f)
        
        # 1. Identify the Subject (The Note itself)
        filename = os.path.basename(filepath).replace(".md", "")
        subject_uri = f"<{BASE_URI}note/{clean_id(filename)}>"
        
        # 2. Process Frontmatter (Metadata)
        # Add the title
        title = post.metadata.get('title', filename)
        triples.append(f'{subject_uri} <{BASE_URI}prop/title> "{escape_literal(title)}" .')
        
        # Add tags
        if 'tags' in post.metadata:
            for tag in post.metadata['tags']:
                triples.append(f'{subject_uri} <{BASE_URI}prop/tag> "{escape_literal(tag)}" .')

        # Add location (Special handling for your Map)
        if 'location' in post.metadata:
            loc = post.metadata['location']
            triples.append(f'{subject_uri} <{BASE_URI}prop/location> "{escape_literal(loc)}" .')

        # Add type
        if 'type' in post.metadata:
            type_val = post.metadata['type']
            triples.append(f'{subject_uri} <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <{BASE_URI}class/{clean_id(type_val)}> .')

        # 3. Process WikiLinks (Relationships)
        # Regex to find [[Link]] or [[Link|Alias]]
        content = post.content
        matches = re.findall(r'\[\[(.*?)\]\]', content)
        
        for match in matches:
            # Handle aliases: "Page Name|Link Text" -> take "Page Name"
            linked_page = match.split('|')[0]
            object_uri = f"<{BASE_URI}note/{clean_id(linked_page)}>"
            
            # Create the relationship
            triples.append(f'{subject_uri} <{BASE_URI}prop/mentions> {object_uri} .')

        # 4. Send to Fuseki (Delete old data for this node, insert new)
        # We use a named graph approach or specific deletion pattern to keep it clean.
        # For simplicity, we will DELETE all facts about this specific subject and re-insert.
        
        if not triples:
            return

        sparql_update = f"""
        DELETE {{ {subject_uri} ?p ?o }} WHERE {{ {subject_uri} ?p ?o }};
        INSERT DATA {{
            {' '.join(triples)}
        }}
        """
        
        response = requests.post(FUSEKI_ENDPOINT, data={'update': sparql_update})
        
        if response.status_code in [200, 204]:
            print(f"✅ Synced: {filename}")
        else:
            print(f"❌ Error {filename}: {response.text}")

    except Exception as e:
        print(f"⚠️ Failed to process {filepath}: {str(e)}")

# Main Loop
print(f"🚀 Connecting to Knowledge Graph at {FUSEKI_ENDPOINT}...")
files = glob.glob(VAULT_PATH, recursive=True)
print(f"📂 Found {len(files)} markdown files. Starting sync...")

for file in files:
    sync_file(file)

print("🎉 Sync Complete!")