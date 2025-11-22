from app import create_app, db
from app.models import User

app = create_app()

# Create a shell context so 'flask shell' has access to db models
@app.shell_context_processor
def make_shell_context():
    return {'db': db, 'User': User}

if __name__ == '__main__':
    # Create DB tables if they don't exist (Simple migration for MVP)
    with app.app_context():
        db.create_all()
        
        # Create a default admin user if none exists
        if not User.query.first():
            print("Creating default admin user...")
            admin = User(username='admin', role='admin')
            admin.set_password('admin') # Change this immediately!
            db.session.add(admin)
            db.session.commit()
            print("Default user: 'admin' / 'admin'")

    app.run(debug=True, port=5000)