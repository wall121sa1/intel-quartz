from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, jsonify
from flask_login import login_required
from app.models import db, Article, CustomEntity, Feed, SystemConfig
from app.services.manager import FeedManager
from app.services.storage import StorageService
from app.services.nlp import NLPService
from datetime import datetime, timezone
import dateutil.parser
from threading import Thread

bp = Blueprint('main', __name__)

# --- HELPER: CONTINUOUS LEARNING ---
def learn_entities(form_data):
    """
    Scans the approved entity lists and adds missing ones to the global dictionary.
    """
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
            
        items = [x.strip() for x in raw_list.split(',') if x.strip()]
        
        for item in items:
            exists = CustomEntity.query.filter_by(text=item, label=label).first()
            if not exists:
                new_entity = CustomEntity(text=item, label=label)
                db.session.add(new_entity)
                new_rules_count += 1
                
    if new_rules_count > 0:
        db.session.commit()
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
    
    # Calculate Time Since Last Run
    last_run_str = SystemConfig.get('last_run_timestamp')
    last_run_display = "Never"
    
    if last_run_str:
        try:
            last_run = dateutil.parser.parse(last_run_str)
            diff = datetime.utcnow() - last_run
            minutes = int(diff.total_seconds() / 60)
            
            if minutes < 1: last_run_display = "Just now"
            elif minutes < 60: last_run_display = f"{minutes} mins ago"
            else: last_run_display = f"{int(minutes/60)} hours ago"
        except:
            last_run_display = "Unknown"

    queue_query = Article.query.join(Feed).filter(Article.status == 'PENDING')

    selected_source = request.args.get('source', '')
    selected_reliability = request.args.get('reliability', '')
    start_raw = request.args.get('start', '')
    end_raw = request.args.get('end', '')

    if selected_source:
        try:
            queue_query = queue_query.filter(Feed.id == int(selected_source))
        except ValueError:
            flash('Invalid source filter provided')

    if selected_reliability:
        queue_query = queue_query.filter(Feed.reliability == selected_reliability)

    def parse_to_utc(value):
        if not value:
            return None
        try:
            parsed = dateutil.parser.isoparse(value)
            if parsed.tzinfo:
                parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
            return parsed
        except (ValueError, TypeError):
            flash('Unable to parse provided date or time filter')
            return None

    start_dt = parse_to_utc(start_raw)
    end_dt = parse_to_utc(end_raw)

    if start_dt:
        queue_query = queue_query.filter(Article.pub_date >= start_dt)
    if end_dt:
        queue_query = queue_query.filter(Article.pub_date <= end_dt)

    queue = queue_query.order_by(Article.pub_date.desc()).limit(100).all()

    sources = Feed.query.order_by(Feed.name).all()
    reliabilities = sorted({feed.reliability for feed in sources if feed.reliability})

    filter_values = {
        'source': selected_source,
        'reliability': selected_reliability,
        'start': start_raw,
        'end': end_raw
    }

    return render_template(
        'main/dashboard.html',
        stats=stats,
        queue=queue,
        last_run=last_run_display,
        last_run_raw=last_run_str,
        sources=sources,
        reliabilities=reliabilities,
        filter_values=filter_values
    )

@bp.route('/fetch-now')
@login_required
def fetch_now():
    def _run_sync(app):
        with app.app_context():
            try:
                stats = FeedManager.sync_all_feeds()
                app.logger.info(
                    "Background sync complete",
                    extra={"added": stats['added'], "skipped": stats['skipped'], "errors": stats['errors']},
                )
            except Exception:
                app.logger.exception("Background sync failed")

    app = current_app._get_current_object()
    Thread(target=_run_sync, args=(app,), daemon=True).start()
    flash("Sync started in the background. Refresh the dashboard in a bit for results.")
    return redirect(url_for('main.dashboard'))

@bp.route('/review/<int:id>')
@login_required
def review(id):
    article = Article.query.get_or_404(id)
    # Import locally to avoid circular dependencies if StandardTag is in models
    from app.models import StandardTag
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
    article.tags = request.form.get('tags')
    
    # FEEDBACK LOOP
    try:
        learn_entities(request.form)
    except Exception as e:
        print(f"Learning Error: {e}") 
    
    try:
        file_path = StorageService.save_article_to_disk(
            article,
            article.source.name,
            article.source.reliability,
            article.source.type_tag
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
    raw_ids = request.form.getlist('article_ids')
    try:
        article_ids = [int(article_id) for article_id in raw_ids]
    except ValueError:
        flash('Invalid article selection')
        return redirect(url_for('main.dashboard'))

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


@bp.route('/queue/status')
@login_required
def queue_status():
    """Return queue metadata so the UI can detect when new articles arrive."""
    return jsonify({
        'pending_count': Article.query.filter_by(status='PENDING').count(),
        'last_run_timestamp': SystemConfig.get('last_run_timestamp') or ''
    })
