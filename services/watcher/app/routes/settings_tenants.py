from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app.models import db, Tenant
from app.routes.settings import bp

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
    db.session.delete(tenant)
    db.session.commit()
    flash('Organization deleted.')
    return redirect(url_for('settings.tenants'))