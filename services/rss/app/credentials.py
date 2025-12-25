import os
from pathlib import Path
from typing import Dict, Tuple


DEFAULT_CREDENTIALS_PATH = "/credentials/credentials.txt"


def credentials_file_path() -> str:
    return os.getenv("CREDENTIALS_FILE", DEFAULT_CREDENTIALS_PATH)


def read_credentials_file(path: str | None = None) -> Dict[str, str]:
    target_path = path or credentials_file_path()
    file_path = Path(target_path)
    if not file_path.exists():
        return {}

    credentials: Dict[str, str] = {}
    for line in file_path.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        credentials[key.strip()] = value.strip()
    return credentials


def write_credentials_file(entries: Dict[str, str], path: str | None = None) -> None:
    target_path = path or credentials_file_path()
    file_path = Path(target_path)
    file_path.parent.mkdir(parents=True, exist_ok=True)

    existing = read_credentials_file(target_path)
    existing.update(entries)

    lines = [f"{key}={value}" for key, value in sorted(existing.items())]
    file_path.write_text("\n".join(lines) + "\n")


def get_bot_env_keys(bot_name: str) -> Tuple[str, str]:
    env_prefix = bot_name.upper()
    return f"{env_prefix}_API_ID", f"{env_prefix}_API_HASH"


def get_bot_credentials(bot_name: str) -> Tuple[str | None, str | None, str]:
    api_id_env, api_hash_env = get_bot_env_keys(bot_name)
    env_api_id = os.getenv(api_id_env)
    env_api_hash = os.getenv(api_hash_env)

    file_credentials = read_credentials_file()
    file_api_id = file_credentials.get(api_id_env)
    file_api_hash = file_credentials.get(api_hash_env)

    api_id = env_api_id or file_api_id
    api_hash = env_api_hash or file_api_hash

    if env_api_id and env_api_hash:
        source = "env"
    elif file_api_id and file_api_hash and not (env_api_id or env_api_hash):
        source = "credentials"
    elif (env_api_id or env_api_hash) and (file_api_id or file_api_hash):
        source = "mixed"
    elif env_api_id or env_api_hash:
        source = "mixed"
    elif file_api_id or file_api_hash:
        source = "mixed"
    else:
        source = "missing"

    return api_id, api_hash, source


def set_bot_credentials(bot_name: str, api_id: str, api_hash: str) -> None:
    api_id_env, api_hash_env = get_bot_env_keys(bot_name)
    entries = {api_id_env: api_id, api_hash_env: api_hash}
    write_credentials_file(entries)
    os.environ[api_id_env] = api_id
    os.environ[api_hash_env] = api_hash
