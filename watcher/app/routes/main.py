from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required
from app import db
from app.models import Article
from app.services.manager import FeedManager
from app.services.storage import StorageService

bp = Blueprint('main', __name__)

@bp.route('/')
@login_required
def dashboard():
    stats = {
        'new': Article.query.filter_by(status='PENDING').count(),
        'approved': Article.query.filter_by(status='APPROVED').count(),
        'rejected': Article.query.filter_by(status='REJECTED').count()
    }
    queue = Article.query.filter_by(status='PENDING').order_by(Article.pub_date.desc()).limit(50).all()
    return render_template('main/dashboard.html', stats=stats, queue=queue)

@bp.route('/fetch-now')
@login_required
def fetch_now():
    try:
        stats = FeedManager.sync_all_feeds()
        flash(f"Sync Complete: {stats['added']} added, {stats['skipped']} skipped.")
    except Exception as e:
        flash(f"Error during sync: {str(e)}")
    return redirect(url_for('main.dashboard'))

@bp.route('/review/<int:id>')
@login_required
def review(id):
    article = Article.query.get_or_404(id)
    return render_template('main/review.html', article=article)

@bp.route('/approve/<int:id>', methods=['POST'])
@login_required
def approve_article(id):
    article = Article.query.get_or_404(id)
    
    article.title = request.form.get('title')
    article.content_edited = request.form.get('content')
    
    # Save comma-separated lists from hidden inputs
    article.organizations = request.form.get('orgs')
    article.people = request.form.get('people')
    article.locations = request.form.get('locs')
    article.events = request.form.get('events') # Capture Events
    
    try:
        file_path = StorageService.save_article_to_disk(
            article, 
            article.source.name, 
            article.source.reliability
        )
        article.status = 'APPROVED'
        db.session.commit()
        flash(f"Published to {file_path}")
    except Exception as e:
        db.session.rollback()
        flash(f"Error saving file: {str(e)}")
        return redirect(url_for('main.review', id=id))

    return redirect(url_for('main.dashboard'))

@bp.route('/reject/<int:id>')
@login_required
def reject_article(id):
    article = Article.query.get_or_404(id)
    article.status = 'REJECTED'
    db.session.commit()
    flash('Article rejected')
    return redirect(url_for('main.dashboard'))