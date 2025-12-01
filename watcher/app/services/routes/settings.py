from app.models import db
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app.models import Feed, User, StandardTag
from app.models import db, Feed, User, StandardTag, CustomEntity
from app.services.nlp import NLPService
import csv
import io
import pyotp
import qrcode
import base64

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

# --- STANDARD TAGS (NEW) ---

@bp.route('/tags')
@login_required
def tags():
    # Allow editors to view, but UI will hide add buttons if we strictly enforce admin
    tags = StandardTag.query.order_by(StandardTag.name).all()
    return render_template('settings/tags.html', tags=tags)

@bp.route('/tags/add', methods=['POST'])
@login_required
def add_tag():
    if current_user.role != 'admin':
        flash('Admin rights required')
        return redirect(url_for('settings.tags'))
        
    name = request.form.get('name').strip()
    if not name: 
        return redirect(url_for('settings.tags'))

    existing = StandardTag.query.filter_by(name=name).first()
    if existing:
        flash('Tag already exists')
        return redirect(url_for('settings.tags'))

    db.session.add(StandardTag(name=name))
    db.session.commit()
    flash('Topic Tag added')
    return redirect(url_for('settings.tags'))

@bp.route('/tags/delete/<int:id>')
@login_required
def delete_tag(id):
    if current_user.role != 'admin':
        return redirect(url_for('settings.tags'))
        
    tag = StandardTag.query.get_or_404(id)
    db.session.delete(tag)
    db.session.commit()
    flash('Topic Tag deleted')
    return redirect(url_for('settings.tags'))

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

@bp.route('/dictionary')
@login_required
def dictionary():
    # Group by label for easier viewing
    entities = CustomEntity.query.order_by(CustomEntity.label, CustomEntity.text).all()
    return render_template('settings/dictionary.html', entities=entities)

@bp.route('/dictionary/add', methods=['POST'])
@login_required
def add_custom_entity():
    text = request.form.get('text').strip()
    label = request.form.get('label')
    
    if text and label:
        existing = CustomEntity.query.filter_by(text=text, label=label).first()
        if not existing:
            db.session.add(CustomEntity(text=text, label=label))
            db.session.commit()
            # Reload NLP model to apply change immediately
            NLPService.reload_model()
            flash(f'Added rule: "{text}" -> {label}')
        else:
            flash('Rule already exists')
            
    return redirect(url_for('settings.dictionary'))

@bp.route('/dictionary/delete/<int:id>')
@login_required
def delete_custom_entity(id):
    entity = CustomEntity.query.get_or_404(id)
    db.session.delete(entity)
    db.session.commit()
    NLPService.reload_model()
    flash('Rule deleted')
    return redirect(url_for('settings.dictionary'))

@bp.route('/dictionary/import', methods=['POST'])
@login_required
def import_dictionary():
    """
    Expects a CSV file with headers: text, label
    """
    file = request.files.get('file')
    if not file:
        flash('No file uploaded')
        return redirect(url_for('settings.dictionary'))

    try:
        stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
        csv_input = csv.DictReader(stream)
        
        added_count = 0
        for row in csv_input:
            text = row.get('text', '').strip()
            label = row.get('label', '').strip().upper()
            
            # Basic validation
            if text and label in ['ORG', 'PERSON', 'LOC', 'GPE', 'EVENT']:
                exists = CustomEntity.query.filter_by(text=text, label=label).first()
                if not exists:
                    db.session.add(CustomEntity(text=text, label=label))
                    added_count += 1
        
        db.session.commit()
        if added_count > 0:
            NLPService.reload_model()
            
        flash(f'Successfully imported {added_count} new rules.')
        
    except Exception as e:
        flash(f'Error processing CSV: {str(e)}')

    return redirect(url_for('settings.dictionary'))

@bp.route('/tenants')
@login_required
def tenants():
    if current_user.role != 'admin':
        flash('Access Denied: Admin rights required.')
        return redirect(url_for('main.dashboard'))
    
    tenants = Tenant.query.order_by(Tenant.name).all()
    return render_template('settings/tenants.html', tenants=tenants)

@bp.route('/tenants/add', methods=['POST'])
@login_required
def add_tenant():
    if current_user.role != 'admin':
        return redirect(url_for('main.dashboard'))

    name = request.form.get('name')
    domain = request.form.get('domain')
    provider = request.form.get('sso_provider')
    client_id = request.form.get('client_id')
    client_secret = request.form.get('client_secret')
    discovery_url = request.form.get('discovery_url')

    if Tenant.query.filter_by(domain=domain).first():
        flash(f"Tenant for domain {domain} already exists.")
        return redirect(url_for('settings.tenants'))

    new_tenant = Tenant(
        name=name,
        domain=domain,
        sso_provider=provider,
        client_id=client_id,
        client_secret=client_secret,
        discovery_url=discovery_url
    )
    
    db.session.add(new_tenant)
    db.session.commit()
    flash(f"Organization '{name}' added successfully.")
    return redirect(url_for('settings.tenants'))

@bp.route('/tenants/delete/<int:id>')
@login_required
def delete_tenant(id):
    if current_user.role != 'admin':
        return redirect(url_for('main.dashboard'))
        
    tenant = Tenant.query.get_or_404(id)
    # Optional: Prevent deleting if users exist? 
    # For now, we allow it (users will just lose SSO access)
    db.session.delete(tenant)
    db.session.commit()
    flash('Organization deleted.')
    return redirect(url_for('settings.tenants'))