from flask import Blueprint, render_template, redirect, url_for, flash, request, session, current_app
from flask_login import login_user, logout_user, current_user
from app.services.auth_manager import AuthManager
from app.models import db, User, Tenant
import pyotp

bp = Blueprint('auth', __name__)

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        email = request.form.get('email')
        
        if not email or '@' not in email:
            flash("Please enter a valid email.")
            return render_template('auth/login_discovery.html')

        try:
            domain = email.split('@')[1]
        except IndexError:
            flash("Invalid email format.")
            return render_template('auth/login_discovery.html')
        
        client, tenant = AuthManager.get_sso_client(domain)
        
        if client:
            session['sso_domain'] = domain
            redirect_uri = url_for('auth.tenant_callback', _external=True)
            return client.authorize_redirect(redirect_uri)
        
        flash(f"No custom SSO found for {domain}. Please use the standard login methods.")
        
        providers = []
        config = current_app.config
        if config.get('GOOGLE_CLIENT_ID'): providers.append('google')
        if config.get('MICROSOFT_CLIENT_ID'): providers.append('microsoft')
        if config.get('OKTA_CLIENT_ID'): providers.append('okta')
        if config.get('CLOUDFLARE_CLIENT_ID'): providers.append('cloudflare')
        
        return render_template('auth/login.html', providers=providers)

    return render_template('auth/login_discovery.html')

@bp.route('/login_legacy')
def login_legacy():
    providers = []
    config = current_app.config
    if config.get('GOOGLE_CLIENT_ID'): providers.append('google')
    if config.get('MICROSOFT_CLIENT_ID'): providers.append('microsoft')
    if config.get('OKTA_CLIENT_ID'): providers.append('okta')
    if config.get('CLOUDFLARE_CLIENT_ID'): providers.append('cloudflare')
    return render_template('auth/login.html', providers=providers)

def finalize_login(user):
    """Helper to check MFA status before logging in"""
    if user.mfa_secret:
        # MFA Enabled: Stash ID and challenge
        session['pre_mfa_user_id'] = user.id
        return redirect(url_for('auth.mfa_challenge'))
    
    # No MFA: Log in immediately
    login_user(user)
    return redirect(url_for('main.dashboard'))

@bp.route('/mfa', methods=['GET', 'POST'])
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
    if not client:
        return redirect(url_for('auth.login'))
    
    redirect_uri = url_for('auth.sso_callback', provider=provider, _external=True)
    return client.authorize_redirect(redirect_uri)

@bp.route('/sso/<provider>/callback')
def sso_callback(provider):
    from app import oauth
    client = oauth.create_client(provider)
    if not client:
        return redirect(url_for('auth.login'))
        
    try:
        token = client.authorize_access_token()
        user_info = token.get('userinfo')
        email = user_info.get('email') or user_info.get('preferred_username')
        
        if not email:
            flash("No email returned.")
            return redirect(url_for('auth.login'))

        allowed = current_app.config['ALLOWED_USERS']
        if allowed and email not in allowed:
            flash("Access Denied.")
            return redirect(url_for('auth.login'))

        user = User.query.filter_by(email=email).first()
        if not user:
            role = 'admin' if User.query.count() == 0 else 'editor'
            user = User(email=email, username=user_info.get('name', email), role=role)
            db.session.add(user)
            db.session.commit()
        
        return finalize_login(user)

    except Exception as e:
        flash(f"Login Failed: {str(e)}")
        return redirect(url_for('auth.login'))