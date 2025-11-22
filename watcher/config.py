import os

basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'you-will-never-guess'
    
    # Database
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'app.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Scheduler
    SCHEDULER_API_ENABLED = True

    # Application Specific
    # Default to a folder named 'vault_data' in the project root for safety
    VAULT_ROOT = os.environ.get('VAULT_ROOT') or os.path.join(basedir, 'vault_data')