from aiogram import Bot, F, Router
from aiogram.enums import ParseMode
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove

from app.config import DEFAULT_CHURCH_NAME
from app.db.repository import save_church_and_complete, save_city, save_name, save_phone
from app.handlers.questionnaire.keyboards import (
    church_keyboard,
    name_use_profile_keyboard,
    phone_keyboard,
)
from app.handlers.questionnaire.service import (
    confirm_suggested_name,
    format_full_name,
    parse_full_name,
    show_pd_step,
    ask_phone,
)
from app.handlers.questionnaire.states import QuestionnaireStates

router = Router()


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
