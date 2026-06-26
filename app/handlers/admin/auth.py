from aiogram.types import CallbackQuery, Message

from app.config import ADMIN_IDS


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def format_access_denied(user_id: int) -> str:
    return (
        "Недостаточно прав. Команда доступна только администраторам бота.\n\n"
        f"Ваш Telegram ID: <code>{user_id}</code>\n"
        "Добавьте этот ID в <code>ADMIN_IDS</code> в .env на сервере и перезапустите контейнер."
    )


async def send_access_denied(message: Message) -> None:
    await message.answer(format_access_denied(message.from_user.id))


async def answer_access_denied(callback: CallbackQuery) -> None:
    from app.services.callbacks import safe_answer_callback

    await safe_answer_callback(
        callback,
        f"Недостаточно прав. Ваш ID: {callback.from_user.id}",
        show_alert=True,
    )
