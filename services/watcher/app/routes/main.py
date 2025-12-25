from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, jsonify, session
from flask_login import login_required
from app.models import db, Article, CustomEntity, Feed, SystemConfig
from sqlalchemy import case, func, or_
from app.services.manager import FeedManager
from app.services.storage import StorageService
from app.services.nlp import NLPService
from app.services.georesolver import GeoResolver
import json
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


def article_type_metrics():
    """Summarize article counts grouped by feed type."""
    rows = (
        db.session.query(
            func.coalesce(Feed.type_tag, 'Uncategorized').label('type_tag'),
            func.count(Article.id).label('total'),
            func.sum(case((Article.status == 'APPROVED', 1), else_=0)).label('approved'),
            func.sum(case((Article.status == 'PENDING', 1), else_=0)).label('pending'),
            func.sum(case((Article.status == 'REJECTED', 1), else_=0)).label('rejected'),
        )
        .join(Article, Article.feed_id == Feed.id)
        .group_by(Feed.type_tag)
        .all()
    )

    return [
        {
            'type_tag': row.type_tag or 'Uncategorized',
            'total': int(row.total or 0),
            'approved': int(row.approved or 0),
            'pending': int(row.pending or 0),
            'rejected': int(row.rejected or 0),
        }
        for row in rows
    ]

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
    last_run_relative = "Never"
    last_run_absolute = "Never"
    last_run_timestamp = ""

    if last_run_str:
        try:
            last_run_dt = dateutil.parser.parse(last_run_str)
            if last_run_dt.tzinfo:
                last_run_dt = last_run_dt.astimezone(timezone.utc)
            else:
                last_run_dt = last_run_dt.replace(tzinfo=timezone.utc)

            now_utc = datetime.now(timezone.utc)
            diff = now_utc - last_run_dt
            minutes = int(diff.total_seconds() / 60)

            if minutes < 1:
                last_run_relative = "Just now"
            elif minutes < 60:
                last_run_relative = f"{minutes} mins ago"
            elif minutes < 1440:
                last_run_relative = f"{int(minutes/60)} hours ago"
            else:
                last_run_relative = f"{int(minutes/1440)} days ago"

            last_run_absolute = last_run_dt.strftime('%Y-%m-%d %H:%M:%S UTC')
            last_run_timestamp = last_run_dt.isoformat()
        except Exception:
            last_run_relative = "Unknown"
            last_run_absolute = last_run_str
            last_run_timestamp = last_run_str

    last_run_stats = None
    last_run_info = None
    raw_stats = SystemConfig.get('last_run_stats')
    if raw_stats:
        try:
            last_run_stats = json.loads(raw_stats)
            last_run_info = (
                f"Last sync added {last_run_stats.get('added', 0)} new articles, "
                f"skipped {last_run_stats.get('skipped', 0)} duplicates, "
                f"and encountered {last_run_stats.get('errors', 0)} errors across "
                f"{last_run_stats.get('feeds', 0)} feeds."
            )
        except (TypeError, ValueError):
            last_run_stats = None

    queue_query = Article.query.join(Feed).filter(Article.status == 'PENDING')

    stored_filters = session.get('dashboard_filters', {})
    has_query_filters = any(
        key in request.args
        for key in ['source', 'reliability', 'start', 'end', 'hide_telegram', 'reset']
    )

    if request.args.get('reset') == '1':
        session.pop('dashboard_filters', None)
        return redirect(url_for('main.dashboard'))

    raw_sources = [src for src in request.args.getlist('source') if src] if has_query_filters else stored_filters.get('sources', [])
    selected_sources = []
    for src in raw_sources:
        if ',' in src:
            selected_sources.extend([part for part in src.split(',') if part])
        else:
            selected_sources.append(src)

    selected_reliabilities = (
        [rel for rel in request.args.getlist('reliability') if rel]
        if has_query_filters else stored_filters.get('reliabilities', [])
    )
    start_raw = request.args.get('start', '') if has_query_filters else stored_filters.get('start', '')
    end_raw = request.args.get('end', '') if has_query_filters else stored_filters.get('end', '')
    hide_telegram = (
        request.args.get('hide_telegram') == 'on'
        if has_query_filters else stored_filters.get('hide_telegram', False)
    )

    session['dashboard_filters'] = {
        'sources': selected_sources,
        'reliabilities': selected_reliabilities,
        'start': start_raw,
        'end': end_raw,
        'hide_telegram': hide_telegram,
    }

    source_ids = []
    country_filters = []
    type_filters = []

    for raw_source in selected_sources:
        if raw_source.startswith('country:'):
            country_filters.append(raw_source.split(':', 1)[1])
        elif raw_source.startswith('type:'):
            type_filters.append(raw_source.split(':', 1)[1])
        elif raw_source.startswith('source:'):
            try:
                source_ids.append(int(raw_source.split(':', 1)[1]))
            except ValueError:
                flash('Invalid source filter provided')
        else:
            try:
                source_ids.append(int(raw_source))
            except ValueError:
                flash('Invalid source filter provided')

    if source_ids:
        queue_query = queue_query.filter(Feed.id.in_(source_ids))
    if country_filters:
        queue_query = queue_query.filter(Feed.country.in_(country_filters))
    if type_filters:
        queue_query = queue_query.filter(Feed.type_tag.in_(type_filters))

    if selected_reliabilities:
        queue_query = queue_query.filter(Feed.reliability.in_(selected_reliabilities))

    if hide_telegram:
        queue_query = queue_query.filter(~or_(
            func.lower(Feed.url).like('%telegram%'),
            func.lower(Feed.url).like('%t.me%'),
            func.lower(Feed.name).like('%telegram%')
        ))

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
    countries = sorted({feed.country for feed in sources if feed.country})
    country_counts = {country: len([feed for feed in sources if feed.country == country]) for country in countries}
    type_tags = sorted({feed.type_tag for feed in sources if feed.type_tag})
    type_counts = {tag: len([feed for feed in sources if feed.type_tag == tag]) for tag in type_tags}
    reliabilities = sorted({feed.reliability for feed in sources if feed.reliability})

    filter_values = {
        'sources': selected_sources,
        'reliabilities': selected_reliabilities,
        'start': start_raw,
        'end': end_raw,
        'hide_telegram': hide_telegram,
    }

    return render_template(
        'main/dashboard.html',
        stats=stats,
        queue=queue,
        last_run_relative=last_run_relative,
        last_run_absolute=last_run_absolute,
        last_run_raw=last_run_timestamp,
        last_run_info=last_run_info,
        sources=sources,
        countries=countries,
        country_counts=country_counts,
        type_tags=type_tags,
        type_counts=type_counts,
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

    # Ensure location suggestions exist for the edited list before exporting sidecars.
    GeoResolver.ensure_locations(GeoResolver.csv_to_list(article.locations))
    
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
            article.source.type_tag,
            article.source.country
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


@bp.route('/statistics')
@login_required
def statistics():
    metrics = article_type_metrics()
    return render_template('main/statistics.html', metrics=metrics)


@bp.route('/statistics/data')
@login_required
def statistics_data():
    return jsonify(article_type_metrics())


@bp.route('/queue/status')
@login_required
def queue_status():
    """Return queue metadata so the UI can detect when new articles arrive."""
    return jsonify({
        'pending_count': Article.query.filter_by(status='PENDING').count(),
        'last_run_timestamp': SystemConfig.get('last_run_timestamp') or ''
    })
