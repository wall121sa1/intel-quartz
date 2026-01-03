from app import create_app, db
from app.models import User
import os
import time
from sqlalchemy import inspect, text
from sqlalchemy.exc import OperationalError

app = create_app()

def wait_for_db():
    """Loops until the database is ready to accept connections."""
    print("DB: Waiting for connection...")
    retries = 30
    while retries > 0:
        try:
            with app.app_context():
                # Try to connect
                db.engine.connect()
                print("DB: Connection successful!")
                return True
        except OperationalError:
            print(f"DB: Not ready yet. Retrying ({retries} left)...")
            time.sleep(2)
            retries -= 1
    return False

def apply_schema_patches():
    """Lightweight schema migrations for existing databases.

    This keeps older deployments aligned with new application fields without
    requiring manual SQL or data loss.
    """
    inspector = inspect(db.engine)

    if 'feed' in inspector.get_table_names():
        feed_columns = {column['name'] for column in inspector.get_columns('feed')}

        if 'country' not in feed_columns:
            print("DB: Adding `country` column to feed table...")
            try:
                db.session.execute(text("ALTER TABLE feed ADD COLUMN country VARCHAR(50)"))
                db.session.commit()
                print("DB: `country` column added to feed table.")
            except Exception as exc:
                db.session.rollback()
                print(f"DB: Failed to add `country` column automatically: {exc}")
    else:
        print("DB: feed table not found; will be created automatically if new database.")

def init():
    with app.app_context():
        # 1. Wait for DB
        if not wait_for_db():
            print("CRITICAL: Could not connect to Database after 60 seconds.")
            exit(1)

        # 2. Create Tables
        print("DB: Creating all tables...")
        db.create_all()

        # 2a. Apply lightweight migrations for existing databases
        apply_schema_patches()
        
        # 3. Create Admin
        if not User.query.first():
            print("DB: No users found. Initializing Admin account...")
            
            # Get creds from Environment
            admin_email = os.environ.get('ADMIN_EMAIL')
            admin_pass = os.environ.get('ADMIN_PASSWORD')

            if not admin_email or not admin_pass:
                print("CRITICAL: ADMIN_EMAIL and ADMIN_PASSWORD must be set via .env.")
                exit(1)
            
            admin = User(email=admin_email, username='Super Admin', role='admin')
            admin.set_password(admin_pass)
            
            db.session.add(admin)
            db.session.commit()
            
            print(f"DB: Admin created successfully! Email: {admin_email}")
        else:
            print("DB: Users exist. Skipping admin creation.")

if __name__ == '__main__':
    init()
