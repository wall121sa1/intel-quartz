import os
from typing import Tuple

def get_bot_env_keys(bot_name: str) -> Tuple[str, str]:
    env_prefix = bot_name.upper()
    return f"{env_prefix}_API_ID", f"{env_prefix}_API_HASH"


def get_bot_credentials(bot_name: str) -> Tuple[str | None, str | None, str]:
    api_id_env, api_hash_env = get_bot_env_keys(bot_name)
    env_api_id = os.getenv(api_id_env)
    env_api_hash = os.getenv(api_hash_env)

    api_id = env_api_id
    api_hash = env_api_hash

    if env_api_id and env_api_hash:
        source = "env"
    elif env_api_id or env_api_hash:
        source = "partial"
    else:
        source = "missing"

    return api_id, api_hash, source
