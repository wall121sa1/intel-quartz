from flask import Blueprint, render_template, redirect, url_for, flash, request, session, current_app
from flask_login import login_user, logout_user, current_user
from flask_limiter.util import get_remote_address
from app import limiter
from app.services.auth_manager import AuthManager
from app.models import db, User, Tenant
import pyotp

bp = Blueprint('auth', __name__)

def finalize_login(user):
    """Helper to check MFA status before logging in"""
    if user.mfa_secret:
        session['pre_mfa_user_id'] = user.id
        return redirect(url_for('auth.mfa_challenge'))
    login_user(user)
    return redirect(url_for('main.dashboard'))

@bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute", key_func=get_remote_address, methods=["POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    # Calculate active providers for the UI
    providers = []
    config = current_app.config
    if config.get('GOOGLE_CLIENT_ID'): providers.append('google')
    if config.get('MICROSOFT_CLIENT_ID'): providers.append('microsoft')
    if config.get('OKTA_CLIENT_ID'): providers.append('okta')
    if config.get('CLOUDFLARE_CLIENT_ID'): providers.append('cloudflare')

    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        # 1. LOCAL PASSWORD LOGIN
        if password:
            user = User.query.filter_by(email=email).first()
            if user and user.check_password(password):
                return finalize_login(user)
            else:
                flash("Invalid email or password.")
                return render_template('auth/login.html', providers=providers)

        # 2. SSO DISCOVERY (If no password provided)
        if not email or '@' not in email:
            flash("Please enter a valid email.")
            return render_template('auth/login.html', providers=providers)

        try:
            domain = email.split('@')[1]
        except IndexError:
            flash("Invalid email format.")
            return render_template('auth/login.html', providers=providers)
        
        client, tenant = AuthManager.get_sso_client(domain)
        
        if client:
            session['sso_domain'] = domain
            redirect_uri = url_for('auth.tenant_callback', _external=True)
            return client.authorize_redirect(redirect_uri)
        
        flash(f"No custom SSO found for {domain}. Please use the buttons below or enter a password.")
        return render_template('auth/login.html', providers=providers)

    return render_template('auth/login.html', providers=providers)

# ... (Keep remaining routes: mfa, callback, logout, sso, sso_callback) ...
# COPY THEM FROM PREVIOUS STEPS OR KEEP EXISTING
# For brevity, I am ensuring the login logic above handles both scenarios.

@bp.route('/mfa', methods=['GET', 'POST'])
@limiter.limit("10 per minute", key_func=get_remote_address, methods=["POST"])
def mfa_challenge():
    if 'pre_mfa_user_id' not in session:
        return redirect(url_for('auth.login'))
    
    if request.method == 'POST':
        code = request.form.get('code')
        user_id = session['pre_mfa_user_id']
        user = User.query.get(user_id)
        
        if user and user.mfa_secret:
            totp = pyotp.TOTP(user.mfa_secret)
            if totp.verify(code):
                session.pop('pre_mfa_user_id')
                login_user(user)
                return redirect(url_for('main.dashboard'))
        
        flash("Invalid code. Please try again.")

    return render_template('auth/mfa_challenge.html')

@bp.route('/login/callback')
@limiter.limit("10 per minute", key_func=get_remote_address)
def tenant_callback():
    domain = session.get('sso_domain')
    if not domain:
        return redirect(url_for('auth.login'))

    client, tenant = AuthManager.get_sso_client(domain)
    if not client:
        flash("SSO Configuration Error.")
        return redirect(url_for('auth.login'))

    try:
        token = client.authorize_access_token()
        user_info = token.get('userinfo')
        email = user_info.get('email') or user_info.get('preferred_username')

        if not email:
            flash("Identity provider did not return an email.")
            return redirect(url_for('auth.login'))

        allowed_users = current_app.config.get('ALLOWED_USERS', [])
        allowed_domains = current_app.config.get('ALLOWED_DOMAINS', [])
        if allowed_users and email not in allowed_users:
            flash("Access Denied.")
            return redirect(url_for('auth.login'))

        domain = email.split('@')[1].lower()
        if allowed_domains and domain not in allowed_domains:
            flash("Access Denied for this domain.")
            return redirect(url_for('auth.login'))

        if email.split('@')[1].lower() != tenant.domain.lower():
            flash("Email domain does not match the configured tenant domain.")
            return redirect(url_for('auth.login'))

        user = User.query.filter_by(email=email).first()
        if not user:
            user = User(email=email, username=user_info.get('name', email), role='editor', tenant_id=tenant.id)
            db.session.add(user)
            db.session.commit()
        
        return finalize_login(user)
        
    except Exception as e:
        flash(f"SSO Failed: {str(e)}")
        return redirect(url_for('auth.login'))

@bp.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('auth.login'))

@bp.route('/sso/<provider>')
def sso_login(provider):
    from app import oauth
    client = oauth.create_client(provider)
    if not client: return redirect(url_for('auth.login'))
    redirect_uri = url_for('auth.sso_callback', provider=provider, _external=True)
    return client.authorize_redirect(redirect_uri)

@bp.route('/sso/<provider>/callback')
@limiter.limit("10 per minute", key_func=get_remote_address)
def sso_callback(provider):
    from app import oauth
    client = oauth.create_client(provider)
    if not client: return redirect(url_for('auth.login'))
    try:
        token = client.authorize_access_token()
        user_info = token.get('userinfo')
        email = user_info.get('email') or user_info.get('preferred_username')
        if not email: return redirect(url_for('auth.login'))

        allowed = current_app.config['ALLOWED_USERS']
        allowed_domains = current_app.config.get('ALLOWED_DOMAINS', [])
        domain = email.split('@')[1].lower()
        if allowed and email not in allowed:
            flash("Access Denied.")
            return redirect(url_for('auth.login'))

        if allowed_domains and domain not in allowed_domains:
            flash("Access Denied for this domain.")
            return redirect(url_for('auth.login'))

        user = User.query.filter_by(email=email).first()
        if not user:
            user = User(email=email, username=user_info.get('name', email), role='editor')
            db.session.add(user)
            db.session.commit()
        return finalize_login(user)
    except Exception as e:
        flash(f"Login Failed: {str(e)}")
        return redirect(url_for('auth.login'))