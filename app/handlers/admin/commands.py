import logging

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import BotCommand, BotCommandScopeAllPrivateChats, BotCommandScopeChat

from app.config import ADMIN_IDS

logger = logging.getLogger(__name__)

USER_COMMANDS = [
    BotCommand(command="start", description="Начать ознакомление"),
]

ADMIN_COMMANDS = [
    BotCommand(command="start", description="Начать ознакомление"),
    BotCommand(command="stats", description="Статистика пользователей"),
    BotCommand(command="send", description="Отправить сообщение"),
    BotCommand(command="cancel", description="Отменить рассылку"),
]


async def setup_bot_commands(bot: Bot) -> None:
    await bot.set_my_commands(USER_COMMANDS, scope=BotCommandScopeAllPrivateChats())

    for admin_id in ADMIN_IDS:
        try:
            await bot.set_my_commands(
                ADMIN_COMMANDS,
                scope=BotCommandScopeChat(chat_id=admin_id),
            )
        except TelegramBadRequest as exc:
            if "chat not found" in (exc.message or "").lower():
                logger.warning(
                    "Не удалось установить команды для admin_id=%s: чат не найден. "
                    "Проверьте ADMIN_IDS и отправьте боту /start с этого аккаунта.",
                    admin_id,
                )
                continue
            raise
