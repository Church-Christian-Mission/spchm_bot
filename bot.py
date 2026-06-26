import asyncio
import os
import time
from dataclasses import dataclass

import aiosqlite
from aiogram import Bot, Dispatcher, F, Router
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import (
    Message,
    CallbackQuery,
    ChatJoinRequest,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.client.default import DefaultBotProperties
from dotenv import load_dotenv

from rich_messages import send_rich_or_html, send_rich_or_html_parts
from texts import (
    RULES_RICH_HTML,
    RULES_FALLBACK_HTML,
    LETTER_PARTS,
    PD_RICH_HTML,
    PD_FALLBACK_HTML,
)


load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
TARGET_CHAT_ID = int(os.getenv("TARGET_CHAT_ID", "0"))

RULES_VERSION = os.getenv("RULES_VERSION", "1.0")
LETTER_VERSION = os.getenv("LETTER_VERSION", "1.0")
PD_VERSION = os.getenv("PD_VERSION", "1.0")

DB_PATH = os.getenv("DB_PATH", "bot.db")

router = Router()


@dataclass
class UserStatus:
    telegram_id: int
    accepted_rules: bool
    accepted_letter: bool
    accepted_pd: bool


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


def letter_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Я прочитал письмо", callback_data="accept_letter")],
        ]
    )


def pd_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Согласен на обработку персональных данных", callback_data="accept_pd")],
            [InlineKeyboardButton(text="❌ Не согласен", callback_data="decline_pd")],
        ]
    )


def join_keyboard(invite_link: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🚪 Подать заявку на вступление", url=invite_link)],
        ]
    )


async def init_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                telegram_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,

                accepted_rules INTEGER DEFAULT 0,
                rules_version TEXT,
                rules_accepted_at INTEGER,

                accepted_letter INTEGER DEFAULT 0,
                letter_version TEXT,
                letter_accepted_at INTEGER,

                accepted_pd INTEGER DEFAULT 0,
                pd_version TEXT,
                pd_accepted_at INTEGER,

                invite_link TEXT,
                joined INTEGER DEFAULT 0,
                joined_at INTEGER,

                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            )
            """
        )
        await db.commit()


async def upsert_user(message_or_callback) -> None:
    user = message_or_callback.from_user
    now = int(time.time())

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO users (
                telegram_id, username, first_name, last_name, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(telegram_id) DO UPDATE SET
                username=excluded.username,
                first_name=excluded.first_name,
                last_name=excluded.last_name,
                updated_at=excluded.updated_at
            """,
            (
                user.id,
                user.username,
                user.first_name,
                user.last_name,
                now,
                now,
            ),
        )
        await db.commit()


async def set_accepted(user_id: int, field: str, version_field: str, accepted_at_field: str, version: str) -> None:
    allowed = {
        "accepted_rules": ("rules_version", "rules_accepted_at"),
        "accepted_letter": ("letter_version", "letter_accepted_at"),
        "accepted_pd": ("pd_version", "pd_accepted_at"),
    }

    if field not in allowed:
        raise ValueError("Invalid field")

    expected_version_field, expected_accepted_at_field = allowed[field]
    if version_field != expected_version_field or accepted_at_field != expected_accepted_at_field:
        raise ValueError("Invalid version/accepted_at field")

    now = int(time.time())

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            f"""
            UPDATE users
            SET {field}=1,
                {version_field}=?,
                {accepted_at_field}=?,
                updated_at=?
            WHERE telegram_id=?
            """,
            (version, now, now, user_id),
        )
        await db.commit()


async def get_status(user_id: int) -> UserStatus | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        row = await db.execute_fetchall(
            """
            SELECT telegram_id, accepted_rules, accepted_letter, accepted_pd
            FROM users
            WHERE telegram_id=?
            """,
            (user_id,),
        )

    if not row:
        return None

    item = row[0]
    return UserStatus(
        telegram_id=item["telegram_id"],
        accepted_rules=bool(item["accepted_rules"]),
        accepted_letter=bool(item["accepted_letter"]),
        accepted_pd=bool(item["accepted_pd"]),
    )


async def save_invite_link(user_id: int, invite_link: str) -> None:
    now = int(time.time())
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            UPDATE users
            SET invite_link=?, updated_at=?
            WHERE telegram_id=?
            """,
            (invite_link, now, user_id),
        )
        await db.commit()


async def mark_joined(user_id: int) -> None:
    now = int(time.time())
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            UPDATE users
            SET joined=1, joined_at=?, updated_at=?
            WHERE telegram_id=?
            """,
            (now, now, user_id),
        )
        await db.commit()


async def has_completed_onboarding(user_id: int) -> bool:
    status = await get_status(user_id)
    return bool(status and status.accepted_rules and status.accepted_letter and status.accepted_pd)


@router.message(CommandStart())
async def start(message: Message) -> None:
    await upsert_user(message)

    await message.answer(
        "Здравствуйте!\n\n"
        "Перед вступлением в чат необходимо пройти короткое ознакомление:\n\n"
        "1. Правила чата\n"
        "2. Письмо / документ\n"
        "3. Согласие на обработку персональных данных\n\n"
        "После этого бот выдаст ссылку для подачи заявки.",
        reply_markup=main_menu_keyboard(),
    )


@router.callback_query(F.data == "show_rules")
async def show_rules(callback: CallbackQuery, bot: Bot) -> None:
    await upsert_user(callback)

    await send_rich_or_html(
        bot=bot,
        bot_token=BOT_TOKEN,
        chat_id=callback.from_user.id,
        rich_html=RULES_RICH_HTML,
        fallback_html=RULES_FALLBACK_HTML,
        reply_markup=rules_keyboard(),
    )

    await callback.answer()


@router.callback_query(F.data == "accept_rules")
async def accept_rules(callback: CallbackQuery, bot: Bot) -> None:
    await upsert_user(callback)
    await set_accepted(
        callback.from_user.id,
        "accepted_rules",
        "rules_version",
        "rules_accepted_at",
        RULES_VERSION,
    )

    await send_rich_or_html_parts(
        bot=bot,
        bot_token=BOT_TOKEN,
        chat_id=callback.from_user.id,
        parts=LETTER_PARTS,
        reply_markup=letter_keyboard(),
    )

    await callback.answer("Правила подтверждены")


@router.callback_query(F.data == "accept_letter")
async def accept_letter(callback: CallbackQuery, bot: Bot) -> None:
    await upsert_user(callback)
    await set_accepted(
        callback.from_user.id,
        "accepted_letter",
        "letter_version",
        "letter_accepted_at",
        LETTER_VERSION,
    )

    await send_rich_or_html(
        bot=bot,
        bot_token=BOT_TOKEN,
        chat_id=callback.from_user.id,
        rich_html=PD_RICH_HTML,
        fallback_html=PD_FALLBACK_HTML,
        reply_markup=pd_keyboard(),
    )

    await callback.answer("Письмо подтверждено")


@router.callback_query(F.data == "decline_pd")
async def decline_pd(callback: CallbackQuery) -> None:
    await callback.message.answer(
        "Без согласия на обработку персональных данных доступ к чату не предоставляется."
    )
    await callback.answer()


@router.callback_query(F.data == "accept_pd")
async def accept_pd(callback: CallbackQuery, bot: Bot) -> None:
    await upsert_user(callback)
    await set_accepted(
        callback.from_user.id,
        "accepted_pd",
        "pd_version",
        "pd_accepted_at",
        PD_VERSION,
    )

    # Ссылка создает не мгновенное вступление, а заявку на вступление.
    # member_limit нельзя использовать вместе с creates_join_request=True.
    invite = await bot.create_chat_invite_link(
        chat_id=TARGET_CHAT_ID,
        name=f"onboarding_{callback.from_user.id}",
        expire_date=int(time.time()) + 60 * 10,
        creates_join_request=True,
    )

    await save_invite_link(callback.from_user.id, invite.invite_link)

    await callback.message.answer(
        "✅ Спасибо! Все этапы пройдены.\n\n"
        "Теперь нажмите кнопку ниже и подайте заявку на вступление. "
        "Если всё пройдено корректно, бот одобрит заявку автоматически.",
        reply_markup=join_keyboard(invite.invite_link),
    )
    await callback.answer("Согласие принято")


@router.chat_join_request()
async def on_chat_join_request(join_request: ChatJoinRequest, bot: Bot) -> None:
    user_id = join_request.from_user.id

    if await has_completed_onboarding(user_id):
        await join_request.approve()
        await mark_joined(user_id)

        try:
            await bot.send_message(
                chat_id=user_id,
                text="🎉 Ваша заявка одобрена. Добро пожаловать в чат!",
            )
        except Exception:
            pass
    else:
        await join_request.decline()

        try:
            await bot.send_message(
                chat_id=user_id,
                text=(
                    "Заявка отклонена, потому что вы ещё не прошли все этапы ознакомления.\n\n"
                    "Нажмите /start и пройдите правила, письмо и согласие."
                ),
            )
        except Exception:
            pass


async def main() -> None:
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is empty")
    if not TARGET_CHAT_ID:
        raise RuntimeError("TARGET_CHAT_ID is empty")

    await init_db()

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    dp = Dispatcher()
    dp.include_router(router)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
