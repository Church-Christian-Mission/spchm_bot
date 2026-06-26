from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, User

from app.config import BOT_TOKEN
from app.db.repository import save_name
from app.handlers.questionnaire.keyboards import (
    name_confirm_keyboard,
    phone_keyboard,
)
from app.handlers.questionnaire.states import QuestionnaireStates
from app.keyboards.onboarding import pd_keyboard
from app.services.rich_messages import send_rich_or_html
from app.texts import PD_FALLBACK_HTML, PD_RICH_HTML


def suggest_name_parts(user: User) -> tuple[str, str, str]:
    return user.last_name or "", user.first_name or "", ""


def format_full_name(surname: str, given_name: str, patronymic: str = "") -> str:
    return " ".join(part for part in (surname, given_name, patronymic) if part).strip()


def parse_full_name(text: str) -> tuple[str, str, str] | None:
    parts = text.strip().split()
    if len(parts) < 2:
        return None
    if len(parts) == 2:
        return parts[0], parts[1], ""
    return parts[0], parts[1], " ".join(parts[2:])


def build_name_prompt(surname: str, given_name: str, patronymic: str) -> str:
    patronymic_line = patronymic if patronymic else "(не указано)"
    return (
        "📝 <b>Анкета перед вступлением в чат</b>\n\n"
        "Проверьте ФИО из вашего профиля Telegram:\n\n"
        f"Фамилия: <b>{surname or '—'}</b>\n"
        f"Имя: <b>{given_name or '—'}</b>\n"
        f"Отчество: <b>{patronymic_line}</b>"
    )


async def start_questionnaire(message: Message, user: User, state: FSMContext) -> None:
    surname, given_name, patronymic = suggest_name_parts(user)
    await state.set_state(QuestionnaireStates.waiting_name_confirm)
    await state.update_data(
        surname=surname,
        given_name=given_name,
        patronymic=patronymic,
    )

    if not surname and not given_name:
        await state.set_state(QuestionnaireStates.waiting_custom_name)
        await message.answer(
            "📝 <b>Анкета перед вступлением в чат</b>\n\n"
            "В профиле Telegram не указано имя.\n"
            "Введите фамилию, имя и отчество (отчество можно не указывать):\n"
            "<i>Например: Иванов Иван Иванович</i>",
            parse_mode=ParseMode.HTML,
        )
        return

    await message.answer(
        build_name_prompt(surname, given_name, patronymic),
        parse_mode=ParseMode.HTML,
        reply_markup=name_confirm_keyboard(),
    )


async def ask_phone(message: Message) -> None:
    await message.answer(
        "📱 Укажите номер телефона — нажмите кнопку ниже, чтобы поделиться контактом.",
        reply_markup=phone_keyboard(),
    )


async def show_pd_step(bot: Bot, chat_id: int) -> None:
    await send_rich_or_html(
        bot=bot,
        bot_token=BOT_TOKEN,
        chat_id=chat_id,
        rich_html=PD_RICH_HTML,
        fallback_html=PD_FALLBACK_HTML,
        reply_markup=pd_keyboard(),
    )


async def confirm_suggested_name(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    surname = data.get("surname", "")
    given_name = data.get("given_name", "")
    patronymic = data.get("patronymic", "")

    if not surname and not given_name:
        await callback.answer("Сначала введите ФИО текстом.", show_alert=True)
        return

    await save_name(callback.from_user.id, surname, given_name, patronymic)
    await state.set_state(QuestionnaireStates.waiting_phone)
    await callback.message.answer(
        f"✅ ФИО сохранено: <b>{format_full_name(surname, given_name, patronymic)}</b>",
        parse_mode=ParseMode.HTML,
    )
    await ask_phone(callback.message)
    await callback.answer()
