
import os
from pathlib import Path

from dotenv import load_dotenv
from cryptography.fernet import Fernet

load_dotenv()


def required_env(name: str) -> str:
    value = os.getenv(name)

    if not value or not value.strip():
        raise RuntimeError(
            f"Missing required environment variable: {name}"
        )

    return value.strip()


BOT_TOKEN = required_env("BOT_TOKEN")

API_ID = int(required_env("API_ID"))
API_HASH = required_env("API_HASH")

ADMIN_ID = int(required_env("ADMIN_ID"))

ENCRYPTION_KEY = required_env("ENCRYPTION_KEY").encode()

try:
    Fernet(ENCRYPTION_KEY)
except (ValueError, TypeError) as exc:
    raise RuntimeError(
        "ENCRYPTION_KEY is invalid. Generate a valid Fernet key."
    ) from exc


BOT_REPLY_TIMEOUT = int(
    os.getenv("BOT_REPLY_TIMEOUT", "25")
)

POST_COMMAND_DELAY = float(
    os.getenv("POST_COMMAND_DELAY", "2")
)

# Database path
DB_PATH = os.getenv("DB_PATH", "/tmp/abbot.db")

db_file = Path(DB_PATH).expanduser().resolve()
db_file.parent.mkdir(parents=True, exist_ok=True)
DB_PATH = str(db_file)

MAX_BOTS = 30

if BOT_REPLY_TIMEOUT <= 0:
    raise RuntimeError("BOT_REPLY_TIMEOUT must be greater than zero.")

if POST_COMMAND_DELAY < 0:
    raise RuntimeError("POST_COMMAND_DELAY cannot be negative.")

if MAX_BOTS != 30:
    raise RuntimeError("MAX_BOTS must remain 30.")
