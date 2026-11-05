import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.environ["BOT_TOKEN"]
API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
ADMIN_ID = int(os.environ["ADMIN_ID"])
ENCRYPTION_KEY = os.environ["ENCRYPTION_KEY"].encode()
BOT_REPLY_TIMEOUT = int(os.getenv("BOT_REPLY_TIMEOUT", "25"))
POST_COMMAND_DELAY = float(os.getenv("POST_COMMAND_DELAY", "2"))
DB_PATH = os.getenv("DB_PATH", "abbot.db")
MAX_BOTS = 30
