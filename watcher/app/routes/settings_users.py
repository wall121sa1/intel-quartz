import re
import secrets
import string

from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app.models import db, User
from app.routes.settings import bp

def _generate_temp_password(length=16):
    alphabet = string.ascii_letters + string.digits + "-_!@#"
    return ''.join(secrets.choice(alphabet) for _ in range(length))

@bp.route('/users')
@login_required
def users():
    if current_user.role != 'admin':
        flash('Access denied')
        return redirect(url_for('main.dashboard'))
    users = User.query.all()
    return render_template('settings/users.html', users=users)

@bp.route('/users/add', methods=['POST'])
@login_required
def add_user():
    if current_user.role != 'admin':
        return redirect(url_for('main.dashboard'))

    email = (request.form.get('email') or '').strip().lower()
    username = request.form.get('username')
    password = request.form.get('password')
    role = request.form.get('role')

    if not email or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        flash('Please provide a valid email address for the new user')
        return redirect(url_for('settings.users'))

    if not username:
        username = email.split('@')[0]

    if User.query.filter_by(email=email).first():
        flash('Email already exists')
        return redirect(url_for('settings.users'))

    if not password:
        flash('Password cannot be empty')
        return redirect(url_for('settings.users'))

    new_user = User(email=email, username=username, role=role)
    if password:
        new_user.set_password(password)
    
    db.session.add(new_user)
    db.session.commit()
    flash(f'User {email} created')
    return redirect(url_for('settings.users'))

@bp.route('/users/delete/<int:id>')
@login_required
def delete_user(id):
    if current_user.role != 'admin':
        return redirect(url_for('main.dashboard'))
    user = User.query.get_or_404(id)
    if user.id == current_user.id:
        flash("Cannot delete yourself")
        return redirect(url_for('settings.users'))
    db.session.delete(user)
    db.session.commit()
    flash('User deleted')
    return redirect(url_for('settings.users'))

@bp.route('/users/reset_mfa/<int:id>')
@login_required
def admin_reset_mfa(id):
    if current_user.role != 'admin':
        return redirect(url_for('main.dashboard'))
    
    user = User.query.get_or_404(id)
    user.mfa_secret = None
    db.session.commit()
    flash(f"MFA disabled for {user.email}")
    return redirect(url_for('settings.users'))

@bp.route('/users/reset_password/<int:id>', methods=['POST'])
@login_required
def admin_reset_password(id):
    if current_user.role != 'admin':
        return redirect(url_for('main.dashboard'))

    user = User.query.get_or_404(id)
    temp_password = _generate_temp_password()
    user.set_password(temp_password)
    user.must_change_password = True
    db.session.commit()
    flash(
        f"Temporary password for {user.email}: {temp_password}. "
        "The user will be prompted to change it on next login."
    )

    return redirect(url_for('settings.users'))

@bp.route('/users/change_role/<int:id>', methods=['POST'])
@login_required
def change_role(id):
    if current_user.role != 'admin':
        return redirect(url_for('main.dashboard'))
        
    user = User.query.get_or_404(id)
    if user.id == current_user.id:
        flash("Cannot change your own role here.")
        return redirect(url_for('settings.users'))

    new_role = request.form.get('role')
    if new_role in ['admin', 'editor']:
        user.role = new_role
        db.session.commit()
        flash(f"Role updated for {user.email}")
        
    return redirect(url_for('settings.users'))