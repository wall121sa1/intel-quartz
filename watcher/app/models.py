from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), index=True, unique=True)
    password_hash = db.Column(db.String(128))
    role = db.Column(db.String(20), default='editor') # 'admin' or 'editor'

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Feed(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    url = db.Column(db.String(255), unique=True)
    reliability = db.Column(db.String(50)) # High, Medium, Low
    vault_id = db.Column(db.String(50), default='default') # Future proofing
    
    # Relationship to articles
    articles = db.relationship('Article', backref='source', lazy='dynamic')

class Article(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    feed_id = db.Column(db.Integer, db.ForeignKey('feed.id'))
    
    # Core Metadata
    title = db.Column(db.String(255))
    url = db.Column(db.String(255), unique=True, index=True)
    pub_date = db.Column(db.DateTime)
    added_date = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Content
    content_raw = db.Column(db.Text)    # Original scrape
    content_edited = db.Column(db.Text) # The version you edit in UI
    
    # Entities (Stored as simple strings for now, or JSON if using Postgres later)
    # We will store them as comma-separated strings for SQLite simplicity
    locations = db.Column(db.Text) 
    organizations = db.Column(db.Text)
    people = db.Column(db.Text)

    # Workflow Status
    # NEW -> PENDING (Scraped) -> APPROVED (Written to Vault) -> REJECTED
    status = db.Column(db.String(20), default='NEW', index=True)
    vault_id = db.Column(db.String(50), default='default')