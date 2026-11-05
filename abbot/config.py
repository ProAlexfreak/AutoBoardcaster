
import os
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


# Telegram controller bot
BOT_TOKEN = required_env("BOT_TOKEN")

# Telegram API credentials
API_ID = int(required_env("API_ID"))
API_HASH = required_env("API_HASH")

# Only this Telegram user can control ABBot
ADMIN_ID = int(required_env("ADMIN_ID"))

# Session encryption key
ENCRYPTION_KEY = required_env("ENCRYPTION_KEY").encode()

try:
    Fernet(ENCRYPTION_KEY)
except (ValueError, TypeError) as exc:
    raise RuntimeError(
        "ENCRYPTION_KEY is invalid. Generate a valid Fernet key."
    ) from exc


# Broadcasting configuration
BOT_REPLY_TIMEOUT = int(
    os.getenv("BOT_REPLY_TIMEOUT", "25")
)

POST_COMMAND_DELAY = float(
    os.getenv("POST_COMMAND_DELAY", "2")
)

# Database
DB_PATH = os.getenv("DB_PATH", "abbot.db")

# Destination bot limit
MAX_BOTS = 30


if BOT_REPLY_TIMEOUT <= 0:
    raise RuntimeError("BOT_REPLY_TIMEOUT must be greater than zero.")

if POST_COMMAND_DELAY < 0:
    raise RuntimeError("POST_COMMAND_DELAY cannot be negative.")

if MAX_BOTS != 30:
    raise RuntimeError("MAX_BOTS must remain 30.")
