from app import create_app, db
from app.models import User
import os
import time
import secrets
import string
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

def init():
    with app.app_context():
        # 1. Wait for DB
        if not wait_for_db():
            print("CRITICAL: Could not connect to Database after 60 seconds.")
            exit(1)

        # 2. Create Tables
        print("DB: Creating all tables...")
        db.create_all()
        
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
            
            admin = User(email=admin_email, username='Super Admin', role='admin')
            admin.set_password(admin_pass)
            
            db.session.add(admin)
            db.session.commit()
            
            print(f"DB: Admin created successfully! Email: {admin_email}")
        else:
            print("DB: Users exist. Skipping admin creation.")

if __name__ == '__main__':
    init()