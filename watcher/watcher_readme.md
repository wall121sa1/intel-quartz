Obsidian Ingest: RSS & NLP Intelligence Pipeline

Obsidian Ingest is a self-hosted web application designed to bridge the gap between global news feeds and your personal knowledge base. It acts as an intelligent middleware that scrapes RSS feeds, uses Natural Language Processing (NLP) to extract entities, allows for human editorial review, and ultimately generates formatted Markdown files for your Obsidian vault.

## Running as Microservices

The web UI and heavy scraping/translation scheduler can run in separate Docker services so the worker does not compete for memory with the UI process. The included `docker-compose.yml` defines two builds:

- `watcher`: serves the Flask UI with the scheduler disabled by default (`ENABLE_SCHEDULER=false`).
- `watcher-worker`: runs only the background scheduler (`ENABLE_SCHEDULER=true`) using the dedicated `watcher/Dockerfile.worker` image.

Start both services together (or scale the worker independently) with:

```bash
cd watcher
docker compose up -d watcher watcher-worker
```

Both services share the same data and vault volumes; adjust the `deploy.resources.limits` fields to tune memory per container.

### Translation Service (LibreTranslate)

The watcher now calls a dedicated LibreTranslate instance for language translation instead of loading translation models inside the Flask process. A LibreTranslate container is bundled in `watcher/docker-compose.yml` and wired to the other services via `LIBRETRANSLATE_URL=http://libretranslate:4000`. When using Docker Compose, bring it up with the rest of the stack so translation requests stay inside the compose network. For standalone setups, you can still run LibreTranslate separately (for example, `docker run -p 4000:5000 libretranslate/libretranslate`) and expose it at `http://localhost:4000`; override `LIBRETRANSLATE_URL` if you choose a different endpoint. Because the service is isolated in the compose network, no API key is required.

🚀 Key Features

Smart Ingestion:

Aggregates news from multiple RSS feeds.

Full-Text Scraping: Uses newspaper3k to bypass short RSS summaries and fetch the actual article content.

State Management: Tracks processed URLs via SQLite to prevent duplicate entries.

NLP & Entity Extraction (spaCy):

Automatically detects People, Organizations, Locations, and Events.

Hybrid AI Engine: Combines statistical modeling with a custom, user-defined Rule Dictionary (Database-backed) for high precision.

Auto-Linking: Automatically wraps detected entities in [[WikiLinks]] within the body text.

Editorial Workflow:

Review Queue: A dashboard to approve or dismiss articles before they enter your vault.

Interactive Editor:

Tag Cloud: Visual management of extracted metadata.

Context Menu: Highlight text in the editor -> Right Click -> Instantly convert to a tag and [[Link]].

Standardized Taxonomy: Administrator-controlled list of "Topic Tags" to keep your vault organized.

Obsidian Ready:

Generates clean Markdown files.

Populates YAML Frontmatter with metadata (Reliability, Source, Dates, Tags).

Organizes files by Source/Year/Month/Day.

🛠️ Tech Stack & Dependencies

Backend: Python 3.10+, Flask (Web Framework)

Database: SQLite (Dev), SQLAlchemy ORM

NLP: spaCy (en_core_web_sm model)

Scraping: feedparser, newspaper3k, lxml_html_clean

Frontend: HTML5, Bootstrap 5, Vanilla JavaScript (No build step required)

Task Management: Flask-APScheduler (for background fetching)

📦 Installation (Local Development)


2. Set up Virtual Environment

python -m venv venv
# Windows
venv\Scripts\activate
# Mac/Linux
source venv/bin/activate


3. Install Dependencies

pip install -r requirements.txt


4. Download NLP Model

We use the small English model for speed and efficiency.

python -m spacy download en_core_web_sm


5. Initialize and Run

python run.py


The app will create app.db automatically.

It will create a default admin user.

Access the app at: http://127.0.0.1:5000

Default Credentials:

Username: admin

Password: admin (Change this immediately in the Users settings!)

📖 Usage Workflow

1. Configure Sources

Navigate to Settings > Feeds. Add your favorite RSS URLs (e.g., http://feeds.bbci.co.uk/news/rss.xml) and assign a "Reliability Score".

2. Teach the AI (Optional)

Navigate to Settings > Dictionary.

Add custom rules (e.g., "Intel Quartz" -> EVENT).

These rules take priority over the standard AI model.

You can use the "Test Bench" on this page to verify how the AI interprets a sentence.

3. Fetch Content

On the Dashboard, click Fetch New Articles.

The system scrapes the full text.

Runs NLP to find entities.

Places items in the Pending Review queue.

4. Editorial Review

Click Review on an article.

Verify Metadata: Check the tag clouds for Locations, People, etc. Click the x to remove bad tags.

Edit Text: Fix formatting or titles.

Add New Entities: Highlight text in the body, Right Click, and select the entity type. This adds it to the metadata AND wraps the text in [[brackets]].

Publish: Click "Publish to Obsidian".

4a. Resolve locations for the map view

Use Settings > Locations to review ambiguous place names, pick a suggested coordinate, or enter latitude/longitude manually. Saved resolutions are written to the sidecar JSON so the Fuseki sync prefers your confirmed positions over automatic guesses.

5. The Output

Approved articles are saved to the vault_data/ directory (or your configured path) in the following structure:
vault_data/{Source_Name}/{Year}/{Month}/{Day}/{Article_Title}.md

⚙️ Configuration

The application is configured via config.py. You can override settings using Environment Variables (recommended for Docker/Production).

Variable

Description

Default

SECRET_KEY

Flask session signing key

you-will-never-guess

DATABASE_URL

Database connection string

sqlite:///app.db

VAULT_ROOT

Where Markdown files are saved

./vault_data

STORAGE_TYPE

Choose `local` (default) or `s3` for where published Markdown is stored.

local

S3_BUCKET / S3_REGION / AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY / AWS_SESSION_TOKEN

AWS configuration used when `STORAGE_TYPE=s3`. You can omit the AWS credential keys when running on EC2/ECS with an IAM role that grants S3 write access.

blank

📂 Project Structure

rss-to-obsidian/
├── app/
│   ├── models.py          # Database Schema (User, Feed, Article, CustomEntity)
│   ├── routes/            # Web Controllers (Main, Auth, Settings)
│   ├── services/          # Core Logic
│   │   ├── manager.py     # Orchestration (Feed syncing)
│   │   ├── nlp.py         # spaCy Pipeline & Rule Engine
│   │   ├── scraper.py     # Newspaper3k Logic
│   │   └── storage.py     # Markdown Generator
│   └── templates/         # HTML Views (Jinja2)
├── vault_data/            # Output folder for .md files
├── config.py              # App Config
├── requirements.txt       # Python Deps
└── run.py                 # Application Entry Point

## Beginner: Deploying to AWS (S3 for vault + RDS for Postgres)

The app already understands AWS services—set a few environment variables and it will push Markdown to S3 and talk to RDS. Here is a minimal, copy-paste friendly path:

1. **Create an S3 bucket** (e.g., `my-quartz-vault`) in your preferred region.
2. **Grant write access** either by:
   - Creating an IAM user with `s3:PutObject` on the bucket and generating access keys, or
   - Attaching an IAM role with the same permission to your EC2/ECS task so you can skip hard-coding keys.
3. **Spin up an RDS Postgres instance**. Note the hostname, database name, username, and password. Your SQLAlchemy URL will look like `postgresql+psycopg2://USER:PASSWORD@HOST:5432/DBNAME`.
4. **Create a `.env` file** next to `watcher/docker-compose.yml` with the AWS settings:
   ```env
   FLASK_ENV=production
   SECRET_KEY=change-me
   ENCRYPTION_KEY=change-me-too
   STORAGE_TYPE=s3
   S3_BUCKET=my-quartz-vault
   S3_REGION=us-east-1
   AWS_ACCESS_KEY_ID=YOUR_KEY          # omit if using an instance/task role
   AWS_SECRET_ACCESS_KEY=YOUR_SECRET   # omit if using an instance/task role
   DATABASE_URL=postgresql+psycopg2://USER:PASSWORD@your-rds-endpoint:5432/DBNAME
   ADMIN_EMAIL=admin@example.com
   ADMIN_PASSWORD=super-strong
   ALLOW_BOOTSTRAP_ADMIN=true
   ```
5. **Run with Docker Compose**:
   ```bash
   docker compose up -d --build
   ```
   The container will save approved articles to `s3://my-quartz-vault/...` and persist app data in your RDS database.
