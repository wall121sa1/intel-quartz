from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app.models import db, StandardTag
from app.routes.settings import bp

@bp.route('/tags')
@login_required
def tags():
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