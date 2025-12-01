from app import create_app, db
from app.models import User
import os

app = create_app()

def init():
    with app.app_context():
        # 1. Create Tables
        print("DB: Creating all tables...")
        db.create_all()
        
        # 2. Create Admin if none exists
        if not User.query.first():
            print("DB: No users found. Creating default Admin...")
            
            # Get creds from Environment or use defaults
            admin_email = os.environ.get('ADMIN_EMAIL', 'admin@local')
            admin_pass = os.environ.get('ADMIN_PASSWORD', 'admin')
            
            admin = User(email=admin_email, username='Super Admin', role='admin')
            admin.set_password(admin_pass)
            
            db.session.add(admin)
            db.session.commit()
            
            print(f"DB: Admin created! Email: {admin_email}")
        else:
            print("DB: Users exist. Skipping admin creation.")

if __name__ == '__main__':
    try:
        init()
    except Exception as e:
        print(f"DB Init Failed (Database might not be ready yet): {e}")
        # We exit with error so Docker knows to restart the container
        exit(1)