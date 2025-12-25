from app import oauth
from app.models import Tenant

class AuthManager:
    @staticmethod
    def get_sso_client(domain):
        """
        Finds the tenant by domain and registers a temporary OAuth client.
        """
        # 1. Lookup Tenant
        tenant = Tenant.query.filter_by(domain=domain).first()
        if not tenant:
            return None, None

        # 2. Check Registry
        # We give the remote app a unique name based on ID
        remote_app_name = f'tenant_{tenant.id}'
        
        # If already registered in this runtime, return it
        if remote_app_name in oauth._registry:
            return oauth.create_client(remote_app_name), tenant

        # 3. Dynamic Registration
        # We assume OIDC standard here. 
        # For non-OIDC providers, you'd need more logic branches.
        print(f"SSO: Registering dynamic client for {domain}...")
        
        oauth.register(
            name=remote_app_name,
            client_id=tenant.client_id,
            client_secret=tenant.client_secret,
            server_metadata_url=tenant.discovery_url,
            client_kwargs={'scope': 'openid email profile'}
        )
        
        return oauth.create_client(remote_app_name), tenant