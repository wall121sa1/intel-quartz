from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app.models import db, Feed, StandardTag, SystemConfig
from app.services.scheduler import SchedulerService
from app.routes.settings import bp

@bp.route('/feeds')
@login_required
def feeds():
    feeds = Feed.query.all()
    current_interval = SystemConfig.get('fetch_interval_minutes', 60)
    tags = StandardTag.query.order_by(StandardTag.name).all()
    return render_template(
        'settings/feeds.html',
        feeds=feeds,
        current_interval=current_interval,
        tags=tags,
        is_admin=current_user.role == 'admin'
    )
    

@bp.route('/feeds/add', methods=['POST'])
@login_required
def add_feed():
    name = request.form.get('name')
    url = request.form.get('url')
    reliability = request.form.get('reliability')
    type_tag = request.form.get('type_tag')
    
    if not name or not url:
        flash('Name and URL are required')
        return redirect(url_for('settings.feeds'))
        
    existing = Feed.query.filter_by(url=url).first()
    if existing:
        flash('Feed already exists')
        return redirect(url_for('settings.feeds'))

    if type_tag:
        exists = StandardTag.query.filter_by(name=type_tag).first()
        if not exists:
            flash('Selected type is not valid')
            return redirect(url_for('settings.feeds'))

    new_feed = Feed(name=name, url=url, reliability=reliability, type_tag=type_tag)
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

@bp.route('/feeds/configure_schedule', methods=['POST'])
@login_required
def configure_schedule():
    interval = request.form.get('interval')
    try:
        interval = int(interval)
        if interval < 0: raise ValueError
        
        SystemConfig.set('fetch_interval_minutes', interval)
        SchedulerService.update_job_interval() # Restart job with new time
        
        flash(f"Auto-pull updated: Every {interval} minutes.")
    except:
        flash("Invalid interval. Please enter a number (0 to disable).")
        
    return redirect(url_for('settings.feeds'))