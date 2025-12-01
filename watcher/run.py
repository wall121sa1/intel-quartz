import os

from app import create_app, db
from app.models import User
from app.services.scheduler import SchedulerService

app = create_app()


def _bootstrap_admin_if_configured():
    """Create an admin account only when explicitly configured."""

    if User.query.first():
        return

    email = os.environ.get('BOOTSTRAP_ADMIN_EMAIL')
    password = os.environ.get('BOOTSTRAP_ADMIN_PASSWORD')
    allow_bootstrap = os.environ.get('ALLOW_BOOTSTRAP_ADMIN', 'false').lower() == 'true'

    if allow_bootstrap and email and password:
        app.logger.warning("Bootstrapping administrator account from environment variables.")
        admin = User(email=email, username=email, role='admin')
        admin.set_password(password)
        db.session.add(admin)
        db.session.commit()
        return

    app.logger.warning(
        "No users exist and bootstrap is disabled. Configure BOOTSTRAP_ADMIN_EMAIL/BOOTSTRAP_ADMIN_PASSWORD and set "
        "ALLOW_BOOTSTRAP_ADMIN=true to create the first admin."
    )


@app.shell_context_processor
def make_shell_context():
    return {'db': db, 'User': User}


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        _bootstrap_admin_if_configured()
        SchedulerService.update_job_interval()

    app.run(debug=app.config.get('DEBUG', False), port=5000)