import os

from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
TARGET_CHAT_ID = int(os.getenv("TARGET_CHAT_ID", "0"))
RULES_VERSION = os.getenv("RULES_VERSION", "1.0")
PD_VERSION = os.getenv("PD_VERSION", "1.0")
DB_PATH = os.getenv("DB_PATH", "bot.db")
USE_RICH_MESSAGES = os.getenv("USE_RICH_MESSAGES", "1") == "1"
ADMIN_IDS = {int(item.strip()) for item in os.getenv("ADMIN_IDS", "").split(",") if item.strip()}

DEFAULT_CHURCH_NAME = "Христианская Миссия"

BROADCAST_DELAY_SEC = 0.05
USERS_PER_PAGE = 15
SEND_USERS_PER_PAGE = 8
STATS_TABLE_PER_PAGE = 5
FORMS_TABLE_PER_PAGE = 8
