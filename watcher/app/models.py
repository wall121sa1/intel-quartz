from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), index=True, unique=True)
    password_hash = db.Column(db.String(128))
    role = db.Column(db.String(20), default='editor')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class StandardTag(db.Model):
    """List of approved topic tags managed by Admin"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)

class Feed(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    url = db.Column(db.String(255), unique=True)
    reliability = db.Column(db.String(50))
    vault_id = db.Column(db.String(50), default='default')
    articles = db.relationship('Article', backref='source', lazy='dynamic')

class CustomEntity(db.Model):
    """
    User-defined dictionary for the NLP Rule Engine.
    These overrides the AI's default guesses.
    """
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(100), nullable=False) # e.g., "Intel Quartz"
    label = db.Column(db.String(20), nullable=False) # e.g., "ORG", "EVENT"
    
    # Composite unique constraint to prevent duplicates
    __table_args__ = (db.UniqueConstraint('text', 'label', name='_text_label_uc'),)

class Article(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    feed_id = db.Column(db.Integer, db.ForeignKey('feed.id'))
    
    title = db.Column(db.String(255))
    url = db.Column(db.String(255), unique=True, index=True)
    pub_date = db.Column(db.DateTime)
    added_date = db.Column(db.DateTime, default=datetime.utcnow)
    
    content_raw = db.Column(db.Text)    # Will store the English/Translated version for processing
    content_edited = db.Column(db.Text) # The user-edited English version
    
    # NEW COLUMNS FOR TRANSLATION
    language = db.Column(db.String(10), default='en') # 'en', 'fa', 'ru'
    content_original = db.Column(db.Text) # The original Farsi/Russian text
    
    # Metadata
    locations = db.Column(db.Text) 
    organizations = db.Column(db.Text)
    people = db.Column(db.Text)
    events = db.Column(db.Text)
    tags = db.Column(db.Text)

    status = db.Column(db.String(20), default='NEW', index=True)
    vault_id = db.Column(db.String(50), default='default')