import asyncio
import os
from typing import Any

import aiosqlite
from aiogram import Bot, F, Router
from aiogram.enums import ParseMode
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    BotCommand,
    BotCommandScopeAllPrivateChats,
    BotCommandScopeChat,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from rich_messages import edit_rich_or_html, send_rich_or_html

DB_PATH = os.getenv("DB_PATH", "bot.db")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_IDS = {int(item.strip()) for item in os.getenv("ADMIN_IDS", "").split(",") if item.strip()}

router = Router()

USERS_PER_PAGE = 15
BROADCAST_DELAY_SEC = 0.05


class SendMessageStates(StatesGroup):
    waiting_user_ref = State()
    waiting_message = State()
    waiting_confirm = State()

STAGES: dict[str, dict[str, str]] = {
    "all": {"title": "Все пользователи", "where": "1=1"},
    "start": {"title": "Нажали /start, правила не приняты", "where": "accepted_rules = 0"},
    "rules": {
        "title": "Правила приняты, согласие нет",
        "where": "accepted_rules = 1 AND accepted_pd = 0",
    },
    "pd": {
        "title": "Согласие принято, в чат не вступили",
        "where": "accepted_pd = 1 AND joined = 0",
    },
    "joined": {"title": "Вступили в чат", "where": "joined = 1"},
}


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def format_user_identity(row: dict[str, Any]) -> str:
    username = row["username"]
    first_name = row["first_name"] or ""
    last_name = row["last_name"] or ""
    full_name = " ".join(part for part in (first_name, last_name) if part).strip()

    if username:
        identity = f"@{username}"
        if full_name:
            identity += f" ({full_name})"
    elif full_name:
        identity = full_name
    else:
        identity = "без имени"

    return identity


def format_user_line_fallback(row: dict[str, Any]) -> str:
    identity = format_user_identity(row)
    stage = user_stage_label(row)
    return f"• {identity} — <code>{row['telegram_id']}</code>\n  {stage}"


def format_user_line_rich(row: dict[str, Any]) -> str:
    identity = format_user_identity(row)
    stage = user_stage_label(row)
    return (
        f"<li><b>{identity}</b> — <code>{row['telegram_id']}</code><br/>{stage}</li>"
    )


def user_stage_label(row: dict[str, Any]) -> str:
    if row["joined"]:
        return "✅ в чате"
    if row["accepted_pd"]:
        return "🔐 согласие ✓, ждёт вступления"
    if row["accepted_rules"]:
        return "📜 правила ✓"
    return "🆕 только /start"


async def fetch_stage_counts() -> dict[str, int]:
    counts: dict[str, int] = {}
    async with aiosqlite.connect(DB_PATH) as db:
        for key, meta in STAGES.items():
            cursor = await db.execute(
                f"SELECT COUNT(*) FROM users WHERE {meta['where']}"
            )
            row = await cursor.fetchone()
            counts[key] = row[0] if row else 0
    return counts


async def fetch_users(stage: str, page: int) -> tuple[list[dict[str, Any]], int]:
    if stage not in STAGES:
        raise ValueError("Unknown stage")

    where = STAGES[stage]["where"]
    offset = page * USERS_PER_PAGE

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        count_cursor = await db.execute(f"SELECT COUNT(*) FROM users WHERE {where}")
        count_row = await count_cursor.fetchone()
        total = count_row[0] if count_row else 0

        cursor = await db.execute(
            f"""
            SELECT
                telegram_id, username, first_name, last_name,
                accepted_rules, accepted_letter, accepted_pd, joined,
                created_at, joined_at
            FROM users
            WHERE {where}
            ORDER BY updated_at DESC
            LIMIT ? OFFSET ?
            """,
            (USERS_PER_PAGE, offset),
        )
        rows = await cursor.fetchall()

    return [dict(row) for row in rows], total


def stats_overview_keyboard(counts: dict[str, int]) -> InlineKeyboardMarkup:
    buttons = [
        ("all", "👥 Все"),
        ("start", "🆕 Старт"),
        ("rules", "📜 Правила"),
        ("pd", "🔐 Согласие"),
        ("joined", "✅ В чате"),
    ]
    rows = [
        [
            InlineKeyboardButton(
                text=f"{label} ({counts[key]})",
                callback_data=f"stats_list:{key}:0",
            )
        ]
        for key, label in buttons
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def stats_list_keyboard(stage: str, page: int, total: int) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    max_page = max((total - 1) // USERS_PER_PAGE, 0)

    nav: list[InlineKeyboardButton] = []
    if page > 0:
        nav.append(
            InlineKeyboardButton(text="⬅️", callback_data=f"stats_list:{stage}:{page - 1}")
        )
    if page < max_page:
        nav.append(
            InlineKeyboardButton(text="➡️", callback_data=f"stats_list:{stage}:{page + 1}")
        )
    if nav:
        rows.append(nav)

    rows.append([InlineKeyboardButton(text="📊 Сводка", callback_data="stats_overview")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_overview_html(counts: dict[str, int]) -> tuple[str, str]:
    rich_html = f"""
<h2>📊 Статистика онбординга</h2>

<table bordered striped>
  <tr><th>Этап</th><th>Кол-во</th></tr>
  <tr><td>👥 Всего в боте</td><td>{counts["all"]}</td></tr>
  <tr><td>🆕 Без правил</td><td>{counts["start"]}</td></tr>
  <tr><td>📜 Правила ✓</td><td>{counts["rules"]}</td></tr>
  <tr><td>🔐 Согласие ✓, не в чате</td><td>{counts["pd"]}</td></tr>
  <tr><td>✅ Вступили в чат</td><td>{counts["joined"]}</td></tr>
</table>

<p>Выберите этап, чтобы посмотреть список людей.</p>
"""

    fallback_html = (
        "<b>📊 Статистика онбординга</b>\n\n"
        f"👥 Всего в боте: <b>{counts['all']}</b>\n"
        f"🆕 Без правил: <b>{counts['start']}</b>\n"
        f"📜 Правила ✓: <b>{counts['rules']}</b>\n"
        f"🔐 Согласие ✓, не в чате: <b>{counts['pd']}</b>\n"
        f"✅ Вступили в чат: <b>{counts['joined']}</b>\n\n"
        "Выберите этап, чтобы посмотреть список людей."
    )
    return rich_html, fallback_html


async def build_list_html(stage: str, page: int) -> tuple[str, str, InlineKeyboardMarkup]:
    users, total = await fetch_users(stage, page)
    title = STAGES[stage]["title"]
    max_page = max((total - 1) // USERS_PER_PAGE, 0)
    keyboard = stats_list_keyboard(stage, page, total)

    if total == 0:
        rich_html = f"<h2>{title}</h2>\n\n<p>Пока никого нет.</p>"
        fallback_html = f"<b>{title}</b>\n\nПока никого нет."
        return rich_html, fallback_html, keyboard

    rich_items = "".join(format_user_line_rich(user) for user in users)
    fallback_lines = "\n".join(format_user_line_fallback(user) for user in users)

    rich_html = (
        f"<h2>{title}</h2>\n"
        f"<p>Страница {page + 1} из {max_page + 1} · всего {total}</p>\n"
        f"<ul>{rich_items}</ul>"
    )
    fallback_html = (
        f"<b>{title}</b>\n"
        f"Страница {page + 1} из {max_page + 1} · всего {total}\n\n"
        f"{fallback_lines}"
    )
    return rich_html, fallback_html, keyboard


async def send_access_denied(message: Message) -> None:
    await message.answer("Недостаточно прав. Команда доступна только администраторам бота.")


@router.message(Command("stats"))
async def stats_command(message: Message, bot: Bot) -> None:
    if not is_admin(message.from_user.id):
        await send_access_denied(message)
        return

    if not ADMIN_IDS:
        await message.answer(
            "Администраторы не настроены. Добавьте ADMIN_IDS в .env "
            "(Telegram ID через запятую)."
        )
        return

    counts = await fetch_stage_counts()
    rich_html, fallback_html = build_overview_html(counts)
    await send_rich_or_html(
        bot=bot,
        bot_token=BOT_TOKEN,
        chat_id=message.from_user.id,
        rich_html=rich_html,
        fallback_html=fallback_html,
        reply_markup=stats_overview_keyboard(counts),
    )


@router.callback_query(F.data == "stats_overview")
async def stats_overview_callback(callback: CallbackQuery, bot: Bot) -> None:
    if not is_admin(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return

    counts = await fetch_stage_counts()
    rich_html, fallback_html = build_overview_html(counts)
    await edit_rich_or_html(
        bot=bot,
        bot_token=BOT_TOKEN,
        message=callback.message,
        rich_html=rich_html,
        fallback_html=fallback_html,
        reply_markup=stats_overview_keyboard(counts),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("stats_list:"))
async def stats_list_callback(callback: CallbackQuery, bot: Bot) -> None:
    if not is_admin(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return

    _, stage, page_raw = callback.data.split(":", 2)
    page = int(page_raw)

    if stage not in STAGES:
        await callback.answer("Неизвестный этап", show_alert=True)
        return

    rich_html, fallback_html, keyboard = await build_list_html(stage, page)
    await edit_rich_or_html(
        bot=bot,
        bot_token=BOT_TOKEN,
        message=callback.message,
        rich_html=rich_html,
        fallback_html=fallback_html,
        reply_markup=keyboard,
    )
    await callback.answer()


def send_target_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="👤 Одному пользователю", callback_data="send_target:one")],
            [InlineKeyboardButton(text="👥 Всем пользователям", callback_data="send_target:all")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="send_cancel")],
        ]
    )


def send_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Отправить", callback_data="send_confirm:yes"),
                InlineKeyboardButton(text="❌ Отмена", callback_data="send_cancel"),
            ]
        ]
    )


async def find_user_by_reference(reference: str) -> dict[str, Any] | None:
    ref = reference.strip()
    if not ref:
        return None

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if ref.startswith("@"):
            cursor = await db.execute(
                """
                SELECT telegram_id, username, first_name, last_name
                FROM users
                WHERE lower(username) = lower(?)
                """,
                (ref[1:],),
            )
        elif ref.isdigit():
            cursor = await db.execute(
                """
                SELECT telegram_id, username, first_name, last_name
                FROM users
                WHERE telegram_id = ?
                """,
                (int(ref),),
            )
        else:
            return None

        row = await cursor.fetchone()

    return dict(row) if row else None


async def fetch_all_user_ids() -> list[int]:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT telegram_id FROM users ORDER BY telegram_id")
        rows = await cursor.fetchall()
    return [row[0] for row in rows]


def format_admin_message(text: str) -> str:
    return f"<b>📢 Сообщение от администрации</b>\n\n{text}"


async def deliver_admin_message(bot: Bot, chat_id: int, text: str) -> bool:
    try:
        await bot.send_message(
            chat_id=chat_id,
            text=format_admin_message(text),
            parse_mode=ParseMode.HTML,
        )
        return True
    except Exception:
        return False


async def clear_send_state(state: FSMContext) -> None:
    await state.clear()


@router.message(Command("send"))
async def send_command(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        await send_access_denied(message)
        return

    if not ADMIN_IDS:
        await message.answer(
            "Администраторы не настроены. Добавьте ADMIN_IDS в .env "
            "(Telegram ID через запятую)."
        )
        return

    await clear_send_state(state)
    await message.answer(
        "Кому отправить сообщение?",
        reply_markup=send_target_keyboard(),
    )


@router.message(Command("cancel"), StateFilter(SendMessageStates))
async def send_cancel_command(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        await send_access_denied(message)
        return

    await clear_send_state(state)
    await message.answer("Отправка отменена.")


@router.callback_query(F.data == "send_cancel")
async def send_cancel_callback(callback: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return

    await clear_send_state(state)
    await callback.message.answer("Отправка отменена.")
    await callback.answer()


@router.callback_query(F.data.startswith("send_target:"))
async def send_target_callback(callback: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return

    target_type = callback.data.split(":", 1)[1]
    if target_type == "one":
        await state.set_state(SendMessageStates.waiting_user_ref)
        await callback.message.answer(
            "Укажите получателя:\n"
            "• Telegram ID (например, <code>123456789</code>)\n"
            "• или @username из базы бота",
            parse_mode=ParseMode.HTML,
        )
    elif target_type == "all":
        user_ids = await fetch_all_user_ids()
        if not user_ids:
            await callback.message.answer("В базе пока нет пользователей.")
            await clear_send_state(state)
        else:
            await state.update_data(target_type="all", recipient_count=len(user_ids))
            await state.set_state(SendMessageStates.waiting_message)
            await callback.message.answer(
                f"Получателей: <b>{len(user_ids)}</b>\n\n"
                "Отправьте текст сообщения. Поддерживается HTML-разметка.",
                parse_mode=ParseMode.HTML,
            )
    else:
        await callback.answer("Неизвестный тип рассылки", show_alert=True)
        return

    await callback.answer()


@router.message(SendMessageStates.waiting_user_ref)
async def send_user_ref_message(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        await send_access_denied(message)
        return

    user = await find_user_by_reference(message.text or "")
    if not user:
        await message.answer(
            "Пользователь не найден в базе бота.\n"
            "Проверьте ID или @username и попробуйте снова.\n"
            "Отмена: /cancel"
        )
        return

    identity = format_user_identity(user)
    await state.update_data(
        target_type="one",
        target_user_id=user["telegram_id"],
        target_label=identity,
        recipient_count=1,
    )
    await state.set_state(SendMessageStates.waiting_message)
    await message.answer(
        f"Получатель: <b>{identity}</b> (<code>{user['telegram_id']}</code>)\n\n"
        "Отправьте текст сообщения. Поддерживается HTML-разметка.",
        parse_mode=ParseMode.HTML,
    )


@router.message(SendMessageStates.waiting_message)
async def send_message_text(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        await send_access_denied(message)
        return

    text = (message.text or message.caption or "").strip()
    if not text:
        await message.answer("Текст сообщения пустой. Отправьте текст или /cancel.")
        return

    data = await state.get_data()
    await state.update_data(message_text=text)
    await state.set_state(SendMessageStates.waiting_confirm)

    if data.get("target_type") == "one":
        recipient_line = (
            f"Получатель: <b>{data.get('target_label')}</b> "
            f"(<code>{data.get('target_user_id')}</code>)"
        )
    else:
        recipient_line = f"Получателей: <b>{data.get('recipient_count', 0)}</b>"

    preview = format_admin_message(text)
    await message.answer(
        f"{recipient_line}\n\n"
        f"<b>Предпросмотр:</b>\n{preview}\n\n"
        "Отправить?",
        parse_mode=ParseMode.HTML,
        reply_markup=send_confirm_keyboard(),
    )


@router.callback_query(F.data == "send_confirm:yes", SendMessageStates.waiting_confirm)
async def send_confirm_callback(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    if not is_admin(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return

    data = await state.get_data()
    text = data.get("message_text", "").strip()
    if not text:
        await callback.answer("Текст сообщения пустой", show_alert=True)
        await clear_send_state(state)
        return

    target_type = data.get("target_type")
    sent = 0
    failed = 0

    if target_type == "one":
        user_id = data.get("target_user_id")
        if user_id and await deliver_admin_message(bot, user_id, text):
            sent = 1
        else:
            failed = 1
    elif target_type == "all":
        for user_id in await fetch_all_user_ids():
            if await deliver_admin_message(bot, user_id, text):
                sent += 1
            else:
                failed += 1
            await asyncio.sleep(BROADCAST_DELAY_SEC)
    else:
        await callback.message.answer("Не удалось определить получателя.")
        await clear_send_state(state)
        await callback.answer()
        return

    await clear_send_state(state)
    await callback.message.answer(
        f"Готово.\nОтправлено: <b>{sent}</b>\nНе доставлено: <b>{failed}</b>",
        parse_mode=ParseMode.HTML,
    )
    await callback.answer("Сообщение отправлено")


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
