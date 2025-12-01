from app import create_app, db
from app.models import User
from app.services.scheduler import SchedulerService # Import this

app = create_app()

@app.shell_context_processor
def make_shell_context():
    return {'db': db, 'User': User}

if __name__ == '__main__':
    with app.app_context():
        # 1. Create Tables
        db.create_all()
        
        # 2. Check for Default Admin
        if not User.query.first():
            print("Initialization: No users found.")
            print("Creating default local admin...")
            
            admin = User(email='admin@localhost', username='Super Admin', role='admin')
            admin.set_password('admin') 
            
            db.session.add(admin)
            db.session.commit()
            
            print("------------------------------------------------")
            print("DEFAULT ADMIN CREATED")
            print("Email:    admin@localhost")
            print("Password: admin")
            print("------------------------------------------------")

        # 3. Refresh Scheduler (Now that DB is definitely ready)
        SchedulerService.update_job_interval()
        
    app.run(debug=True, port=5000)