import os
import time

import aiosqlite
from aiogram import Bot, F, Router
from aiogram.filters import StateFilter
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    User,
)

from rich_messages import send_rich_or_html
from texts import PD_FALLBACK_HTML, PD_RICH_HTML

DB_PATH = os.getenv("DB_PATH", "bot.db")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
DEFAULT_CHURCH_NAME = "Христианская Миссия"

router = Router()


class QuestionnaireStates(StatesGroup):
    waiting_name_confirm = State()
    waiting_custom_name = State()
    waiting_phone = State()
    waiting_city = State()
    waiting_church_choice = State()
    waiting_custom_church = State()


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


def name_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Верно", callback_data="form_name:confirm")],
            [InlineKeyboardButton(text="✏️ Ввести свои", callback_data="form_name:custom")],
        ]
    )


def name_use_profile_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Использовать из профиля", callback_data="form_name:confirm")],
        ]
    )


def church_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"✅ {DEFAULT_CHURCH_NAME}",
                    callback_data="form_church:default",
                )
            ],
            [InlineKeyboardButton(text="✏️ Указать другую", callback_data="form_church:custom")],
        ]
    )


def phone_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📱 Поделиться номером", request_contact=True)],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def build_name_prompt(surname: str, given_name: str, patronymic: str) -> str:
    patronymic_line = patronymic if patronymic else "(не указано)"
    return (
        "📝 <b>Анкета перед вступлением в чат</b>\n\n"
        "Проверьте ФИО из вашего профиля Telegram:\n\n"
        f"Фамилия: <b>{surname or '—'}</b>\n"
        f"Имя: <b>{given_name or '—'}</b>\n"
        f"Отчество: <b>{patronymic_line}</b>"
    )


async def save_name(user_id: int, surname: str, given_name: str, patronymic: str) -> None:
    now = int(time.time())
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            UPDATE users
            SET surname=?, given_name=?, patronymic=?, updated_at=?
            WHERE telegram_id=?
            """,
            (surname, given_name, patronymic or None, now, user_id),
        )
        await db.commit()


async def save_phone(user_id: int, phone: str) -> None:
    now = int(time.time())
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET phone=?, updated_at=? WHERE telegram_id=?",
            (phone, now, user_id),
        )
        await db.commit()


async def save_city(user_id: int, city: str) -> None:
    now = int(time.time())
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET city=?, updated_at=? WHERE telegram_id=?",
            (city, now, user_id),
        )
        await db.commit()


async def save_church_and_complete(user_id: int, church_name: str) -> None:
    now = int(time.time())
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            UPDATE users
            SET church_name=?, questionnaire_completed=1,
                questionnaire_completed_at=?, updated_at=?
            WHERE telegram_id=?
            """,
            (church_name, now, now, user_id),
        )
        await db.commit()


def pd_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Согласен на обработку персональных данных",
                    callback_data="accept_pd",
                )
            ],
            [InlineKeyboardButton(text="❌ Не согласен", callback_data="decline_pd")],
        ]
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


@router.callback_query(
    F.data == "form_name:confirm",
    StateFilter(QuestionnaireStates.waiting_name_confirm, QuestionnaireStates.waiting_custom_name),
)
async def form_name_confirm(callback: CallbackQuery, state: FSMContext) -> None:
    await confirm_suggested_name(callback, state)


@router.callback_query(F.data == "form_name:custom", QuestionnaireStates.waiting_name_confirm)
async def form_name_custom(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(QuestionnaireStates.waiting_custom_name)
    await callback.message.answer(
        "Введите фамилию, имя и отчество (отчество можно не указывать):\n"
        "<i>Например: Иванов Иван Иванович</i>\n\n"
        "Или используйте данные из профиля Telegram:",
        parse_mode=ParseMode.HTML,
        reply_markup=name_use_profile_keyboard(),
    )
    await callback.answer()


@router.message(QuestionnaireStates.waiting_custom_name)
async def form_custom_name_message(message: Message, state: FSMContext) -> None:
    parsed = parse_full_name(message.text or "")
    if not parsed:
        await message.answer(
            "Нужно указать минимум фамилию и имя.\n"
            "<i>Например: Иванов Иван</i>",
            parse_mode=ParseMode.HTML,
        )
        return

    surname, given_name, patronymic = parsed
    await save_name(message.from_user.id, surname, given_name, patronymic)
    await state.set_state(QuestionnaireStates.waiting_phone)
    await message.answer(
        f"✅ ФИО сохранено: <b>{format_full_name(surname, given_name, patronymic)}</b>",
        parse_mode=ParseMode.HTML,
    )
    await ask_phone(message)


@router.message(QuestionnaireStates.waiting_phone, F.contact)
async def form_phone_contact(message: Message, state: FSMContext) -> None:
    contact = message.contact
    if not contact or contact.user_id != message.from_user.id:
        await message.answer("Пожалуйста, поделитесь своим номером через кнопку ниже.")
        return

    phone = contact.phone_number
    if not phone:
        await message.answer("Не удалось получить номер телефона. Попробуйте ещё раз.")
        return

    await save_phone(message.from_user.id, phone)
    await state.set_state(QuestionnaireStates.waiting_city)
    await message.answer(
        f"✅ Телефон сохранён: <b>{phone}</b>\n\nВведите ваш город:",
        parse_mode=ParseMode.HTML,
        reply_markup=ReplyKeyboardRemove(),
    )


@router.message(QuestionnaireStates.waiting_phone)
async def form_phone_invalid(message: Message) -> None:
    await message.answer(
        "Для продолжения нажмите кнопку «📱 Поделиться номером».",
        reply_markup=phone_keyboard(),
    )


@router.message(QuestionnaireStates.waiting_city)
async def form_city_message(message: Message, state: FSMContext) -> None:
    city = (message.text or "").strip()
    if not city:
        await message.answer("Введите название города.")
        return

    await save_city(message.from_user.id, city)
    await state.set_state(QuestionnaireStates.waiting_church_choice)
    await message.answer(
        f"✅ Город сохранён: <b>{city}</b>\n\n"
        "Укажите название вашей поместной церкви:",
        parse_mode=ParseMode.HTML,
        reply_markup=church_keyboard(),
    )


@router.callback_query(F.data == "form_church:default", QuestionnaireStates.waiting_church_choice)
async def form_church_default(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    await save_church_and_complete(callback.from_user.id, DEFAULT_CHURCH_NAME)
    await state.clear()
    await callback.message.answer(
        f"✅ Церковь: <b>{DEFAULT_CHURCH_NAME}</b>\n\n"
        "Анкета заполнена. Остался последний шаг — согласие на обработку персональных данных.",
        parse_mode=ParseMode.HTML,
    )
    await show_pd_step(bot, callback.from_user.id)
    await callback.answer()


@router.callback_query(F.data == "form_church:custom", QuestionnaireStates.waiting_church_choice)
async def form_church_custom(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(QuestionnaireStates.waiting_custom_church)
    await callback.message.answer("Введите название вашей поместной церкви:")
    await callback.answer()


@router.message(QuestionnaireStates.waiting_custom_church)
async def form_custom_church_message(message: Message, state: FSMContext, bot: Bot) -> None:
    church_name = (message.text or "").strip()
    if not church_name:
        await message.answer("Введите название церкви.")
        return

    await save_church_and_complete(message.from_user.id, church_name)
    await state.clear()
    await message.answer(
        f"✅ Церковь: <b>{church_name}</b>\n\n"
        "Анкета заполнена. Остался последний шаг — согласие на обработку персональных данных.",
        parse_mode=ParseMode.HTML,
    )
    await show_pd_step(bot, message.from_user.id)
