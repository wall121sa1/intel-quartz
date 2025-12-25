from flask import Blueprint

# 1. Create Blueprint
bp = Blueprint('settings', __name__)

# 2. Import modules (This registers the routes on the blueprint)
# The modules will import 'bp' from here.
from app.routes import (
    settings_feeds,
    settings_tags,
    settings_dict,
    settings_users,
    settings_mfa,
    settings_tenants,
    settings_geolocations
)