from flask import render_template, redirect, url_for, flash, request, session
from flask_login import login_required, current_user
from app.models import db
from app.routes.settings import bp
import pyotp
import qrcode
import io
import base64

@bp.route('/mfa/setup', methods=['GET', 'POST'])
@login_required
def mfa_setup():
    if request.method == 'POST':
        secret = session.get('mfa_setup_secret')
        code = request.form.get('code')
        
        if not secret:
            flash("Session expired. Please try again.")
            return redirect(url_for('settings.mfa_setup'))
            
        totp = pyotp.TOTP(secret)
        if totp.verify(code):
            current_user.mfa_secret = secret
            db.session.commit()
            session.pop('mfa_setup_secret', None)
            flash("Two-Factor Authentication Enabled!")
            return redirect(url_for('main.dashboard'))
        else:
            flash("Invalid code. Please try again.")

    # GET Request
    secret = pyotp.random_base32()
    session['mfa_setup_secret'] = secret
    
    uri = pyotp.totp.TOTP(secret).provisioning_uri(
        name=current_user.email, 
        issuer_name="Obsidian Ingest"
    )
    
    img = qrcode.make(uri)
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    qr_b64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
    
    return render_template('settings/mfa_setup.html', qr_b64=qr_b64, secret=secret)

@bp.route('/mfa/disable')
@login_required
def mfa_disable():
    current_user.mfa_secret = None
    db.session.commit()
    flash("Two-Factor Authentication Disabled.")
    return redirect(url_for('settings.users'))