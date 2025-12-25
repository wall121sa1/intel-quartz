from app import create_app, db
from app.models import User
import os
import time
import secrets
import string
from pathlib import Path
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

def generate_secure_password(length=24):
    """Generates a secure random password."""
    alphabet = string.ascii_letters + string.digits + "-_!@#"
    return ''.join(secrets.choice(alphabet) for i in range(length))

def write_credentials_file(email: str, password: str, filename: str = "credentials.txt"):
    """Write generated credentials to a local file."""
    credentials_path = Path(os.environ.get("CREDENTIALS_FILE", filename))
    credentials_path.parent.mkdir(parents=True, exist_ok=True)

    existing: dict[str, str] = {}
    if credentials_path.exists():
        for line in credentials_path.read_text(encoding="utf-8").splitlines():
            if not line or line.lstrip().startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            existing[key] = value

    existing["WATCHER_ADMIN_EMAIL"] = email
    existing["WATCHER_ADMIN_PASSWORD"] = password

    content_lines = ["# Quartz bootstrap credentials"]
    content_lines.extend(f"{key}={value}" for key, value in existing.items())
    credentials_path.write_text("\n".join(content_lines) + "\n", encoding="utf-8")
    os.chmod(credentials_path, 0o600)
    print(f"SECURITY NOTICE: Saved generated credentials to {credentials_path.resolve()}")

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
            
            # SECURITY: If no credentials provided, generate them securely.
            # Never fall back to hardcoded strings.
            if not admin_email:
                admin_email = "admin@localhost"
                print("NOTICE: ADMIN_EMAIL not set. Defaulting to 'admin@localhost'")
                
            if not admin_pass:
                admin_pass = generate_secure_password()
                print("SECURITY NOTICE: ADMIN_PASSWORD not set.")
                print("="*60)
                print(f"GENERATED SECURE PASSWORD: {admin_pass}")
                print("="*60)
                print("Please log in and change this immediately or set ADMIN_PASSWORD env var.")
                write_credentials_file(admin_email, admin_pass)
            
            admin = User(email=admin_email, username='Super Admin', role='admin')
            admin.set_password(admin_pass)
            
            db.session.add(admin)
            db.session.commit()
            
            print(f"DB: Admin created successfully! Email: {admin_email}")
        else:
            print("DB: Users exist. Skipping admin creation.")

if __name__ == '__main__':
    init()
