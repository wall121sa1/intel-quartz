import os
from typing import Optional

from cryptography.fernet import Fernet

basedir = os.path.abspath(os.path.dirname(__file__))


def _get_required_secret(env_key: str, default: Optional[str] = None) -> str:
    """Retrieve a secret value, failing fast in production when unset."""

    environment = os.environ.get('FLASK_ENV', 'production').lower()
    allow_default = environment in {'development', 'testing'} and default is not None

    value = os.environ.get(env_key)
    if value:
        return value

    if allow_default:
        return default

    raise RuntimeError(
        f"Missing required secret `{env_key}`. Set it in the environment before starting the app."
    )


def _get_encryption_key() -> str:
    """Return a stable encryption key, refusing to run in production without one."""

    environment = os.environ.get('FLASK_ENV', 'production').lower()
    key = os.environ.get('ENCRYPTION_KEY')
    if key:
        return key

    if environment in {'development', 'testing'}:
        # Safe fallback for local runs only. Production must provide a fixed key.
        return Fernet.generate_key().decode()

    raise RuntimeError("ENCRYPTION_KEY is required in production.")


class Config:
    DEBUG = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    SECRET_KEY = _get_required_secret('SECRET_KEY', default='dev-secret-key')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///' + os.path.join(basedir, 'app.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SCHEDULER_API_ENABLED = True
    VAULT_ROOT = os.environ.get('VAULT_ROOT') or os.path.join(basedir, 'vault_data')

    # Security
    ALLOWED_USERS = [user for user in os.environ.get('ALLOWED_USERS', '').split(',') if user]
    ALLOWED_DOMAINS = [domain.strip().lower() for domain in os.environ.get('ALLOWED_DOMAINS', '').split(',') if domain.strip()]

    # ENCRYPTION KEY (Critical for SecurityService)
    ENCRYPTION_KEY = _get_encryption_key()

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