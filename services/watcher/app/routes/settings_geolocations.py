from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required
from sqlalchemy import and_, or_

from app.models import db, LocationResolution
from app.routes.settings import bp
from app.services.georesolver import GeoResolver


@bp.route('/geolocations')
@login_required
def geolocations():
    flagged = (
        LocationResolution.query.filter(
            or_(
                LocationResolution.needs_review.is_(True),
                LocationResolution.latitude.is_(None),
                LocationResolution.longitude.is_(None),
            )
        )
        .order_by(LocationResolution.name)
        .all()
    )

    resolved = (
        LocationResolution.query.filter(
            and_(
                LocationResolution.needs_review.is_(False),
                LocationResolution.latitude.is_not(None),
                LocationResolution.longitude.is_not(None),
            )
        )
        .order_by(LocationResolution.updated_at.desc())
        .limit(200)
        .all()
    )

    return render_template(
        'settings/geolocations.html',
        flagged=flagged,
        resolved=resolved,
    )


@bp.route('/geolocations/<int:loc_id>/update', methods=['POST'])
@login_required
def update_geolocation(loc_id: int):
    record = LocationResolution.query.get_or_404(loc_id)
    try:
        latitude = float(request.form.get('latitude'))
        longitude = float(request.form.get('longitude'))
    except (TypeError, ValueError):
        flash('Latitude and longitude must be numeric values.')
        return redirect(url_for('settings.geolocations'))

    GeoResolver.save_manual_resolution(record, latitude, longitude)
    flash(f"Saved manual coordinates for {record.name}.")
    return redirect(url_for('settings.geolocations'))


@bp.route('/geolocations/<int:loc_id>/refresh', methods=['POST'])
@login_required
def refresh_geolocation(loc_id: int):
    record = LocationResolution.query.get_or_404(loc_id)
    GeoResolver.refresh_record(record)
    db.session.commit()
    flash(f"Updated suggestions for {record.name}.")
    return redirect(url_for('settings.geolocations'))
