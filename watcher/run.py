import os
import secrets
import string
from app import create_app, db
from app.models import User
from app.services.scheduler import SchedulerService

app = create_app()

@app.shell_context_processor
def make_shell_context():
    return {'db': db, 'User': User}

def generate_secure_password(length=16):
    """Generate a secure random password with mixed characters."""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return ''.join(secrets.choice(alphabet) for i in range(length))

if __name__ == '__main__':
    with app.app_context():
        # 1. Create Tables
        db.create_all()
        
        # 2. Check for Default Admin
        # We only create an admin if the database is completely empty (no users).
        if not User.query.first():
            print("Initialization: No users found.")
            print("Creating default local admin...")
            
            # Fetch from Env or Generate Default
            admin_email = os.environ.get('ADMIN_EMAIL', 'admin@localhost')
            admin_pass = os.environ.get('ADMIN_PASSWORD')
            
            is_generated = False
            if not admin_pass:
                admin_pass = generate_secure_password()
                is_generated = True
            
            try:
                admin = User(email=admin_email, username='Super Admin', role='admin')
                admin.set_password(admin_pass)
                
                db.session.add(admin)
                db.session.commit()
                
                print("\n" + "="*60)
                print("IMPORTANT: DEFAULT ADMIN ACCOUNT CREATED")
                print("="*60)
                print(f"Email:    {admin_email}")
                print(f"Password: {admin_pass}")
                print("-" * 60)
                if is_generated:
                    print("(!) This password was generated automatically.")
                    print("(!) Please log in and CHANGE IT IMMEDIATELY.")
                else:
                    print("(!) Configured via environment variable.")
                print("="*60 + "\n")
                
            except Exception as e:
                print(f"Error creating admin: {e}")

        # 3. Refresh Scheduler
        SchedulerService.update_job_interval()
        
    app.run(debug=True, host='0.0.0.0', port=5000)