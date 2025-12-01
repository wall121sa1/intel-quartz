import os
from cryptography.fernet import Fernet

basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'you-will-never-guess'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///' + os.path.join(basedir, 'app.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SCHEDULER_API_ENABLED = True
    VAULT_ROOT = os.environ.get('VAULT_ROOT') or os.path.join(basedir, 'vault_data')

    # Security
    ALLOWED_USERS = os.environ.get('ALLOWED_USERS', '').split(',')

    # ENCRYPTION KEY (Critical for SecurityService)
    # In production, set this env var! 
    # If missing locally, we generate a temporary one (WARNING: Restarts will make old data unreadable if key changes)
    ENCRYPTION_KEY = os.environ.get('ENCRYPTION_KEY') or Fernet.generate_key().decode()

    # --- SSO PROVIDERS ---
    GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID')
    GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET')
    MICROSOFT_CLIENT_ID = os.environ.get('MICROSOFT_CLIENT_ID')
    MICROSOFT_CLIENT_SECRET = os.environ.get('MICROSOFT_CLIENT_SECRET')
    MICROSOFT_TENANT_ID = os.environ.get('MICROSOFT_TENANT_ID', 'common')
    OKTA_CLIENT_ID = os.environ.get('OKTA_CLIENT_ID')
    OKTA_CLIENT_SECRET = os.environ.get('OKTA_CLIENT_SECRET')
    OKTA_DOMAIN = os.environ.get('OKTA_DOMAIN')
    CLOUDFLARE_CLIENT_ID = os.environ.get('CLOUDFLARE_CLIENT_ID')
    CLOUDFLARE_CLIENT_SECRET = os.environ.get('CLOUDFLARE_CLIENT_SECRET')
    CLOUDFLARE_DOMAIN = os.environ.get('CLOUDFLARE_DOMAIN')