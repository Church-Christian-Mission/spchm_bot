from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from app.db.repository import upsert_user
from app.keyboards.onboarding import main_menu_keyboard

router = Router()


@router.message(CommandStart())
async def start(message: Message) -> None:
    await upsert_user(message)

    await message.answer(
        "Здравствуйте!\n\n"
        "Перед вступлением в чат необходимо пройти короткое ознакомление:\n\n"
        "1. Правила чата\n"
        "2. Анкета (ФИО, телефон, город, церковь)\n"
        "3. Согласие на обработку персональных данных\n\n"
        "После этого бот выдаст ссылку для подачи заявки.",
        reply_markup=main_menu_keyboard(),
    )
