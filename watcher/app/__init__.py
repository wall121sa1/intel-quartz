from flask import Flask
from flask_login import LoginManager
from flask_migrate import Migrate
from config import Config
from app.models import db, User

migrate = Migrate()
login = LoginManager()
login.login_view = 'auth.login'

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    migrate.init_app(app, db)
    login.init_app(app)

    # Register Blueprints (Direct imports to avoid recursion)
    from app.routes.main import bp as bp_main
    from app.routes.auth import bp as bp_auth
    from app.routes.settings import bp as bp_settings
    
    app.register_blueprint(bp_main)
    app.register_blueprint(bp_auth, url_prefix='/auth')
    app.register_blueprint(bp_settings, url_prefix='/settings')

    return app

@login.user_loader
def load_user(id):
    return User.query.get(int(id))