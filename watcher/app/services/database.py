import sqlite3
from pathlib import Path

DB_PATH = "processed_articles.db"

def init_db():
    """Initialize the database table if it doesn't exist."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS articles
                 (url TEXT PRIMARY KEY, processed_date TEXT)''')
    conn.commit()
    conn.close()

def is_processed(url: str) -> bool:
    """Check if the URL has already been processed."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT 1 FROM articles WHERE url=?", (url,))
    result = c.fetchone()
    conn.close()
    return result is not None

def mark_as_processed(url: str):
    """Mark a URL as processed."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    from datetime import datetime
    c.execute("INSERT OR IGNORE INTO articles VALUES (?, ?)", 
              (url, datetime.now().isoformat()))
    conn.commit()
    conn.close()