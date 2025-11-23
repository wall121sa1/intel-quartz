Obsidian Ingest: RSS & NLP Intelligence Pipeline

Obsidian Ingest is a self-hosted web application designed to bridge the gap between global news feeds and your personal knowledge base. It acts as an intelligent middleware that scrapes RSS feeds, uses Natural Language Processing (NLP) to extract entities, allows for human editorial review, and ultimately generates formatted Markdown files for your Obsidian vault.

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
