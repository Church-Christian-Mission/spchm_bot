from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from app.config import DEFAULT_CHURCH_NAME


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
