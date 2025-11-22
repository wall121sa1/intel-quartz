from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.models import Feed, User

# Define Blueprint here
bp = Blueprint('settings', __name__)

# --- FEEDS ---
@bp.route('/feeds')
@login_required
def feeds():
    feeds = Feed.query.all()
    return render_template('settings/feeds.html', feeds=feeds)

@bp.route('/feeds/add', methods=['POST'])
@login_required
def add_feed():
    name = request.form.get('name')
    url = request.form.get('url')
    reliability = request.form.get('reliability')
    
    if not name or not url:
        flash('Name and URL are required')
        return redirect(url_for('settings.feeds'))
        
    existing = Feed.query.filter_by(url=url).first()
    if existing:
        flash('Feed already exists')
        return redirect(url_for('settings.feeds'))

    new_feed = Feed(name=name, url=url, reliability=reliability)
    db.session.add(new_feed)
    db.session.commit()
    flash(f'Feed "{name}" added successfully')
    return redirect(url_for('settings.feeds'))

@bp.route('/feeds/delete/<int:id>')
@login_required
def delete_feed(id):
    feed = Feed.query.get_or_404(id)
    db.session.delete(feed)
    db.session.commit()
    flash('Feed deleted')
    return redirect(url_for('settings.feeds'))

# --- USERS ---
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

    username = request.form.get('username')
    password = request.form.get('password')
    role = request.form.get('role')

    if User.query.filter_by(username=username).first():
        flash('Username already exists')
        return redirect(url_for('settings.users'))

    new_user = User(username=username, role=role)
    new_user.set_password(password)
    db.session.add(new_user)
    db.session.commit()
    flash(f'User {username} created')
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