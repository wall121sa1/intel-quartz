from app import create_app, db
from app.models import User

app = create_app()

@app.shell_context_processor
def make_shell_context():
    return {'db': db, 'User': User}

if __name__ == '__main__':
    with app.app_context():
        # Create tables if they don't exist
        db.create_all()
        
        # Check if we have any users
        if not User.query.first():
            print("Initialization: No users found.")
            print("Creating default local admin...")
            
            admin = User(email='admin@localhost', username='Super Admin', role='admin')
            admin.set_password('admin') # Default Password
            
            db.session.add(admin)
            db.session.commit()
            
            print("------------------------------------------------")
            print("DEFAULT ADMIN CREATED")
            print("Email:    admin@localhost")
            print("Password: admin")
            print("PLEASE CHANGE THIS PASSWORD AFTER LOGGING IN")
            print("------------------------------------------------")
        
    app.run(debug=True, port=5000)