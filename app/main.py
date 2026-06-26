import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from app.config import BOT_TOKEN, TARGET_CHAT_ID, log_admin_config
from app.db import init_db
from app.handlers.admin import router as admin_router
from app.handlers.admin.commands import setup_bot_commands
from app.handlers.onboarding import router as onboarding_router
from app.handlers.questionnaire import router as questionnaire_router


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is empty")
    if not TARGET_CHAT_ID:
        raise RuntimeError("TARGET_CHAT_ID is empty")

    log_admin_config()

    await init_db()

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(onboarding_router)
    dp.include_router(questionnaire_router)
    dp.include_router(admin_router)

    await setup_bot_commands(bot)
    await dp.start_polling(bot)


def run() -> None:
    asyncio.run(main())
