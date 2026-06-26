from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📜 Ознакомиться с правилами", callback_data="show_rules")],
        ]
    )


def rules_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Я ознакомился с правилами", callback_data="accept_rules")],
        ]
    )


def join_keyboard(invite_link: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🚪 Подать заявку на вступление", url=invite_link)],
        ]
    )


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
