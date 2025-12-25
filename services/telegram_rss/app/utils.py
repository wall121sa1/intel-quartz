# app/utils.py
from datetime import datetime, date
import json

def telethon_to_safe_json(message) -> dict:
    """
    Convert Telethon message to JSON-safe dict:
    - datetime/date -> ISO string
    """
    def default(o):
        if isinstance(o, (datetime, date)):
            return o.isoformat()
        # fallback: string repr
        return str(o)

    # Telethon .to_dict() -> Python objects (inc. datetimes)
    data = message.to_dict()
    # round-trip through json.dumps/loads with custom serializer
    return json.loads(json.dumps(data, default=default))
