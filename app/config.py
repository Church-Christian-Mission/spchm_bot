import logging
import os
import re

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
TARGET_CHAT_ID = int(os.getenv("TARGET_CHAT_ID", "0"))
RULES_VERSION = os.getenv("RULES_VERSION", "1.0")
PD_VERSION = os.getenv("PD_VERSION", "1.0")
DB_PATH = os.getenv("DB_PATH", "bot.db")
USE_RICH_MESSAGES = os.getenv("USE_RICH_MESSAGES", "1") == "1"


def _parse_admin_ids(raw: str) -> set[int]:
    ids: set[int] = set()
    for item in raw.split(","):
        token = item.split("#", 1)[0].strip().strip('"').strip("'")
        if not token:
            continue
        match = re.match(r"-?\d+", token)
        if match:
            ids.add(int(match.group()))
    return ids


ADMIN_IDS = _parse_admin_ids(os.getenv("ADMIN_IDS", ""))

DEFAULT_CHURCH_NAME = "Христианская Миссия"

BROADCAST_DELAY_SEC = 0.05
USERS_PER_PAGE = 15
SEND_USERS_PER_PAGE = 8
STATS_TABLE_PER_PAGE = 5
FORMS_TABLE_PER_PAGE = 8


def log_admin_config() -> None:
    if ADMIN_IDS:
        logger.info("ADMIN_IDS loaded: %d admin(s)", len(ADMIN_IDS))
    else:
        logger.warning("ADMIN_IDS is empty — admin commands will be unavailable")
