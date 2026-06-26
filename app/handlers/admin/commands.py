from aiogram import Bot
from aiogram.types import BotCommand, BotCommandScopeAllPrivateChats, BotCommandScopeChat

from app.config import ADMIN_IDS

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
        await bot.set_my_commands(
            ADMIN_COMMANDS,
            scope=BotCommandScopeChat(chat_id=admin_id),
        )
