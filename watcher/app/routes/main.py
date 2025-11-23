from app.models import db
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required
from app.models import Article, StandardTag
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
    queue = Article.query.filter_by(status='PENDING').order_by(Article.pub_date.desc()).limit(100).all()
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

# --- REVIEW ---

@bp.route('/review/<int:id>')
@login_required
def review(id):
    article = Article.query.get_or_404(id)
    # Fetch standard tags for autocomplete
    standard_tags = StandardTag.query.order_by(StandardTag.name).all()
    return render_template('main/review.html', article=article, standard_tags=standard_tags)

@bp.route('/approve/<int:id>', methods=['POST'])
@login_required
def approve_article(id):
    article = Article.query.get_or_404(id)
    
    article.title = request.form.get('title')
    article.content_edited = request.form.get('content')
    article.organizations = request.form.get('orgs')
    article.people = request.form.get('people')
    article.locations = request.form.get('locs')
    article.events = request.form.get('events')
    article.tags = request.form.get('tags') # Save Tags
    
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

# --- ACTIONS ---

@bp.route('/dismiss/<int:id>')
@login_required
def dismiss_article(id):
    article = Article.query.get_or_404(id)
    article.status = 'REJECTED'
    db.session.commit()
    flash('Article dismissed')
    return redirect(url_for('main.dashboard'))

@bp.route('/dismiss-bulk', methods=['POST'])
@login_required
def dismiss_bulk():
    article_ids = request.form.getlist('article_ids')
    if not article_ids:
        flash('No articles selected')
        return redirect(url_for('main.dashboard'))
    
    count = Article.query.filter(Article.id.in_(article_ids)).update(
        {Article.status: 'REJECTED'}, 
        synchronize_session=False
    )
    db.session.commit()
    flash(f'{count} articles dismissed')
    return redirect(url_for('main.dashboard'))

@bp.route('/restore/<int:id>')
@login_required
def restore_article(id):
    article = Article.query.get_or_404(id)
    article.status = 'PENDING'
    db.session.commit()
    flash('Article restored to queue')
    return redirect(url_for('main.history'))

@bp.route('/history')
@login_required
def history():
    approved = Article.query.filter_by(status='APPROVED').order_by(Article.added_date.desc()).limit(50).all()
    rejected = Article.query.filter_by(status='REJECTED').order_by(Article.added_date.desc()).limit(50).all()
    return render_template('main/history.html', approved=approved, rejected=rejected)