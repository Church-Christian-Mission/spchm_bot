from aiogram.types import Message

from app.config import ADMIN_IDS


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


async def send_access_denied(message: Message) -> None:
    await message.answer("Недостаточно прав. Команда доступна только администраторам бота.")
