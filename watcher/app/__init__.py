import os

from flask import Flask
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from config import Config
from app.models import db, User
from authlib.integrations.flask_client import OAuth
from app.services.scheduler import SchedulerService

migrate = Migrate()
login = LoginManager()
login.login_view = 'auth.login'
oauth = OAuth()
limiter = Limiter(key_func=get_remote_address, default_limits=["200 per hour"], storage_uri="memory://")

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    migrate.init_app(app, db)
    login.init_app(app)
    oauth.init_app(app)
    limiter.init_app(app)

    # --- Dynamic SSO Registration ---
    
    # 1. Google
    if app.config.get('GOOGLE_CLIENT_ID'):
        oauth.register(
            name='google',
            server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
            client_kwargs={'scope': 'openid email profile'}
        )

    # 2. Microsoft
    if app.config.get('MICROSOFT_CLIENT_ID'):
        tenant = app.config.get('MICROSOFT_TENANT_ID')
        oauth.register(
            name='microsoft',
            server_metadata_url=f'https://login.microsoftonline.com/{tenant}/v2.0/.well-known/openid-configuration',
            client_kwargs={'scope': 'openid email profile User.Read'}
        )

    # 3. Okta
    if app.config.get('OKTA_CLIENT_ID') and app.config.get('OKTA_DOMAIN'):
        domain = app.config.get('OKTA_DOMAIN')
        oauth.register(
            name='okta',
            server_metadata_url=f'https://{domain}/.well-known/openid-configuration',
            client_kwargs={'scope': 'openid email profile'}
        )

    # 4. Cloudflare
    if app.config.get('CLOUDFLARE_CLIENT_ID') and app.config.get('CLOUDFLARE_DOMAIN'):
        domain = app.config.get('CLOUDFLARE_DOMAIN')
        oauth.register(
            name='cloudflare',
            server_metadata_url=f'https://{domain}/cdn-cgi/access/sso/oidc/{app.config["CLOUDFLARE_CLIENT_ID"]}/.well-known/openid-configuration',
            client_kwargs={'scope': 'openid email profile'}
        )

    from app.routes.main import bp as bp_main
    from app.routes.auth import bp as bp_auth
    from app.routes.settings import bp as bp_settings
    
    app.register_blueprint(bp_main)
    app.register_blueprint(bp_auth, url_prefix='/auth')
    app.register_blueprint(bp_settings, url_prefix='/settings')

    # Run the scheduler only when explicitly enabled. This allows scraper/translation
    # workloads to run inside a dedicated worker container instead of the main web
    # process to reduce memory pressure.
    if os.getenv("ENABLE_SCHEDULER", "false").lower() == "true":
        SchedulerService.init_app(app)
    else:
        app.logger.info("Scheduler disabled (ENABLE_SCHEDULER != true).")

    return app

@login.user_loader
def load_user(id):
    return User.query.get(int(id))
