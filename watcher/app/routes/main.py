from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required
from app.models import db, Article, CustomEntity
from app.services.manager import FeedManager
from app.services.storage import StorageService
from app.services.nlp import NLPService # Needed to reload model
from app.models import db, Article, CustomEntity, SystemConfig # Added SystemConfig
from datetime import datetime
import dateutil.parser

bp = Blueprint('main', __name__)

# --- HELPER: CONTINUOUS LEARNING ---
def learn_entities(form_data):
    """
    Scans the approved entity lists and adds missing ones to the global dictionary.
    """
    # Map form fields to NLP labels
    mappings = {
        'orgs': 'ORG',
        'people': 'PERSON',
        'locs': 'LOC',
        'events': 'EVENT',
        'tags': 'TAG'
    }
    
    new_rules_count = 0
    
    for field, label in mappings.items():
        raw_list = form_data.get(field)
        if not raw_list:
            continue
            
        # Split "Apple, Microsoft" -> ["Apple", "Microsoft"]
        items = [x.strip() for x in raw_list.split(',') if x.strip()]
        
        for item in items:
            # Check if this rule already exists
            # We use a case-insensitive check logic for better UX, 
            # though DB is strictly case sensitive usually.
            exists = CustomEntity.query.filter_by(text=item, label=label).first()
            
            if not exists:
                # LEARN IT!
                new_entity = CustomEntity(text=item, label=label)
                db.session.add(new_entity)
                new_rules_count += 1
                
    if new_rules_count > 0:
        db.session.commit()
        # Critical: Tell NLP to reload the new rules immediately
        NLPService.reload_model()
        print(f"Feedback Loop: Learned {new_rules_count} new entities.")

# --- ROUTES ---

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

@bp.route('/review/<int:id>')
@login_required
def review(id):
    article = Article.query.get_or_404(id)
    # We assume StandardTag import is handled in settings, or we can fetch them if needed for UI
    from app.models import StandardTag
    standard_tags = StandardTag.query.order_by(StandardTag.name).all()
    return render_template('main/review.html', article=article, standard_tags=standard_tags)

@bp.route('/approve/<int:id>', methods=['POST'])
@login_required
def approve_article(id):
    article = Article.query.get_or_404(id)
    
    # 1. Update Article Data
    article.title = request.form.get('title')
    article.content_edited = request.form.get('content')
    article.organizations = request.form.get('orgs')
    article.people = request.form.get('people')
    article.locations = request.form.get('locs')
    article.events = request.form.get('events')
    article.tags = request.form.get('tags')
    
    # 2. FEEDBACK LOOP: Learn from user corrections
    try:
        learn_entities(request.form)
    except Exception as e:
        print(f"Learning Error: {e}") 
        # Don't crash approval if learning fails
    
    # 3. Save to Disk
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

@bp.route('/')
@login_required
def dashboard():
    stats = {
        'new': Article.query.filter_by(status='PENDING').count(),
        'approved': Article.query.filter_by(status='APPROVED').count(),
        'rejected': Article.query.filter_by(status='REJECTED').count()
    }
    
    # Calculate Time Since Last Run
    last_run_str = SystemConfig.get('last_run_timestamp')
    last_run_display = "Never"
    
    if last_run_str:
        last_run = dateutil.parser.parse(last_run_str)
        diff = datetime.utcnow() - last_run
        minutes = int(diff.total_seconds() / 60)
        
        if minutes < 1: last_run_display = "Just now"
        elif minutes < 60: last_run_display = f"{minutes} mins ago"
        else: last_run_display = f"{int(minutes/60)} hours ago"

    queue = Article.query.filter_by(status='PENDING').order_by(Article.pub_date.desc()).limit(100).all()
    
    return render_template('main/dashboard.html', stats=stats, queue=queue, last_run=last_run_display)