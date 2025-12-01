from datetime import datetime
from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash # Re-imported
from sqlalchemy.dialects.sqlite import JSON

db = SQLAlchemy()

class Tenant(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    domain = db.Column(db.String(100), unique=True, index=True)
    sso_provider = db.Column(db.String(20)) 
    client_id = db.Column(db.String(255))
    client_secret = db.Column(db.String(255))
    discovery_url = db.Column(db.String(255))

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64))
    email = db.Column(db.String(120), index=True, unique=True)
    role = db.Column(db.String(20), default='editor')
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenant.id'), nullable=True)
    mfa_secret = db.Column(db.String(32))
    
    # RESTORED: Local Password Support
    password_hash = db.Column(db.String(128))

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        if not self.password_hash:
            return False # User is SSO-only
        return check_password_hash(self.password_hash, password)

class StandardTag(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)

class CustomEntity(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(100), nullable=False)
    label = db.Column(db.String(20), nullable=False)
    __table_args__ = (db.UniqueConstraint('text', 'label', name='_text_label_uc'),)

class Feed(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    url = db.Column(db.String(255), unique=True)
    reliability = db.Column(db.String(50))
    vault_id = db.Column(db.String(50), default='default')
    articles = db.relationship('Article', backref='source', lazy='dynamic')

class Article(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    feed_id = db.Column(db.Integer, db.ForeignKey('feed.id'))
    title = db.Column(db.String(255))
    url = db.Column(db.String(255), unique=True, index=True)
    pub_date = db.Column(db.DateTime)
    added_date = db.Column(db.DateTime, default=datetime.utcnow)
    content_raw = db.Column(db.Text)
    content_edited = db.Column(db.Text)
    language = db.Column(db.String(10), default='en')
    content_original = db.Column(db.Text)
    locations = db.Column(db.Text) 
    organizations = db.Column(db.Text)
    people = db.Column(db.Text)
    events = db.Column(db.Text)
    tags = db.Column(db.Text)
    status = db.Column(db.String(20), default='NEW', index=True)
    vault_id = db.Column(db.String(50), default='default')