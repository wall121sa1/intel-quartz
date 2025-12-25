import argparse
from pathlib import Path

import yaml
from dotenv import load_dotenv
from telethon import TelegramClient

from app.credentials import get_bot_credentials, get_bot_env_keys

def load_config(path: str = "config.yaml") -> dict:
    with open(path, "r") as f:
        return yaml.safe_load(f)


def find_bot(config: dict, bot_name: str) -> dict:
    for bot in config.get("bots", []):
        if bot.get("name") == bot_name:
            return bot
    raise SystemExit(f"Bot '{bot_name}' not found in config.yaml")


def get_bot_credentials_for_login(bot_name: str):
    api_id_env, api_hash_env = get_bot_env_keys(bot_name)
    api_id, api_hash, _ = get_bot_credentials(bot_name)

    if not api_id or not api_hash:
        raise SystemExit(
            f"Missing env vars {api_id_env} / {api_hash_env} for bot '{bot_name}'.\n"
            "Set them in your environment, credentials file, or in a .env file."
        )

    return int(api_id), api_hash


async def login_bot(bot_name: str):
    # Load config + .env
    load_dotenv()
    config = load_config()
    bot_cfg = find_bot(config, bot_name)
    api_id, api_hash = get_bot_credentials_for_login(bot_name)

    session_name = bot_cfg.get("session_name")
    if not session_name:
        raise SystemExit(f"Bot '{bot_name}' has no session_name in config.yaml")

    # Ensure sessions directory exists
    sessions_dir = Path("sessions")
    sessions_dir.mkdir(exist_ok=True)

    # Store session file under ./sessions/<session_name>.session
    session_path = sessions_dir / session_name

    print(f"Logging in bot '{bot_name}'")
    print(f"- session file: {session_path}.session")
    print(f"- theme: {bot_cfg.get('theme')}")
    print("You will be prompted for your phone number and Telegram login code.")
    print("If you have 2FA enabled, you will also be asked for your password.\n")

    client = TelegramClient(
        session=session_path.as_posix(),
        api_id=api_id,
        api_hash=api_hash,
    )

    async with client:
        # This will trigger the login flow if not authorized yet
        await client.start()
        me = await client.get_me()
        print("\nLogin successful!")
        print(f"Logged in as: {me.username or me.first_name} (id={me.id})")
        print(f"Session saved to: {session_path}.session")


def main():
    parser = argparse.ArgumentParser(
        description="Login a Telegram bot/user and create a Telethon session file."
    )
    parser.add_argument(
        "bot_name",
        help="Name of the bot as defined in config.yaml (e.g. ru_crime_bot)",
    )
    args = parser.parse_args()

    import asyncio

    asyncio.run(login_bot(args.bot_name))


if __name__ == "__main__":
    main()
