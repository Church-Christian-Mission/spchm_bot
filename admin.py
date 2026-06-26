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
SEND_USERS_PER_PAGE = 8
STATS_TABLE_PER_PAGE = 5
BROADCAST_DELAY_SEC = 0.05

STAGE_ORDER = ["all", "start", "rules", "form", "pd", "joined"]
STAGE_LABELS = {
    "all": "👥 Все пользователи",
    "start": "🆕 Без правил",
    "rules": "📜 Правила ✓, анкета нет",
    "form": "📝 Анкета ✓, согласие нет",
    "pd": "🔐 Согласие ✓, не в чате",
    "joined": "✅ Вступили в чат",
}

_stats_pages: dict[int, dict[str, int]] = {}


class SendMessageStates(StatesGroup):
    waiting_message = State()
    waiting_confirm = State()

STAGES: dict[str, dict[str, str]] = {
    "all": {"title": "Все пользователи", "where": "1=1"},
    "start": {"title": "Нажали /start, правила не приняты", "where": "accepted_rules = 0"},
    "rules": {
        "title": "Правила приняты, анкета не заполнена",
        "where": "accepted_rules = 1 AND questionnaire_completed = 0",
    },
    "form": {
        "title": "Анкета заполнена, согласие нет",
        "where": "accepted_rules = 1 AND questionnaire_completed = 1 AND accepted_pd = 0",
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
    form_name = " ".join(
        part
        for part in (
            row.get("surname") or "",
            row.get("given_name") or "",
            row.get("patronymic") or "",
        )
        if part
    ).strip()

    username = row.get("username")
    first_name = row.get("first_name") or ""
    last_name = row.get("last_name") or ""
    full_name = form_name or " ".join(
        part for part in (first_name, last_name) if part
    ).strip()

    if username:
        identity = f"@{username}"
        if full_name:
            identity += f" ({full_name})"
    elif full_name:
        identity = full_name
    else:
        identity = "без имени"

    return identity


def user_stage_label(row: dict[str, Any]) -> str:
    if row["joined"]:
        return "✅ в чате"
    if row["accepted_pd"]:
        return "🔐 согласие ✓, ждёт вступления"
    if row.get("questionnaire_completed"):
        return "📝 анкета ✓"
    if row["accepted_rules"]:
        return "📜 правила ✓"
    return "🆕 только /start"


def default_stats_pages() -> dict[str, int]:
    return {key: 0 for key in STAGE_ORDER}


def get_admin_stats_pages(admin_id: int) -> dict[str, int]:
    return _stats_pages.setdefault(admin_id, default_stats_pages())


def reset_admin_stats_pages(admin_id: int) -> None:
    _stats_pages[admin_id] = default_stats_pages()


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


async def fetch_users(
    stage: str,
    page: int,
    per_page: int = USERS_PER_PAGE,
) -> tuple[list[dict[str, Any]], int]:
    if stage not in STAGES:
        raise ValueError("Unknown stage")

    where = STAGES[stage]["where"]
    offset = page * per_page

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        count_cursor = await db.execute(f"SELECT COUNT(*) FROM users WHERE {where}")
        count_row = await count_cursor.fetchone()
        total = count_row[0] if count_row else 0

        cursor = await db.execute(
            f"""
            SELECT
                telegram_id, username, first_name, last_name,
                surname, given_name, patronymic,
                accepted_rules, accepted_letter, accepted_pd, joined,
                questionnaire_completed,
                created_at, joined_at
            FROM users
            WHERE {where}
            ORDER BY updated_at DESC
            LIMIT ? OFFSET ?
            """,
            (per_page, offset),
        )
        rows = await cursor.fetchall()

    return [dict(row) for row in rows], total


async def fetch_user_by_id(telegram_id: int) -> dict[str, Any] | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT
                telegram_id, username, first_name, last_name,
                surname, given_name, patronymic,
                accepted_rules, accepted_letter, accepted_pd, joined
            FROM users
            WHERE telegram_id = ?
            """,
            (telegram_id,),
        )
        row = await cursor.fetchone()

    return dict(row) if row else None


    return dict(row) if row else None


def build_stage_users_table_rich(users: list[dict[str, Any]]) -> str:
    if not users:
        return "<p>Пока никого нет.</p>"

    rows = "".join(
        (
            "<tr>"
            f"<td>{format_user_identity(user)}</td>"
            f"<td><code>{user['telegram_id']}</code></td>"
            f"<td>{user_stage_label(user)}</td>"
            "</tr>"
        )
        for user in users
    )
    return (
        "<table bordered striped>"
        "<tr><th>Пользователь</th><th>ID</th><th>Этап</th></tr>"
        f"{rows}"
        "</table>"
    )


def build_stage_users_table_fallback(users: list[dict[str, Any]]) -> str:
    if not users:
        return "Пока никого нет."

    lines = [
        f"• {format_user_identity(user)} — {user['telegram_id']} · {user_stage_label(user)}"
        for user in users
    ]
    return "\n".join(lines)


def build_stage_details_rich(
    stage: str,
    users: list[dict[str, Any]],
    total: int,
    page: int,
) -> str:
    max_page = max((total - 1) // STATS_TABLE_PER_PAGE, 0)
    page_info = f"<p>Страница {page + 1} из {max_page + 1} · всего {total}</p>" if total else ""
    return (
        f"<details>\n"
        f"  <summary>{STAGE_LABELS[stage]} ({total})</summary>\n"
        f"  {build_stage_users_table_rich(users)}\n"
        f"  {page_info}\n"
        f"</details>"
    )


def build_stage_details_fallback(
    stage: str,
    users: list[dict[str, Any]],
    total: int,
    page: int,
) -> str:
    max_page = max((total - 1) // STATS_TABLE_PER_PAGE, 0)
    page_info = (
        f"Страница {page + 1} из {max_page + 1} · всего {total}\n\n"
        if total
        else "\n"
    )
    return (
        f"<b>{STAGE_LABELS[stage]} ({total})</b>\n"
        f"{page_info}"
        f"{build_stage_users_table_fallback(users)}"
    )


def stats_pagination_keyboard(pages: dict[str, int], totals: dict[str, int]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []

    for stage in STAGE_ORDER:
        page = pages[stage]
        total = totals[stage]
        max_page = max((total - 1) // STATS_TABLE_PER_PAGE, 0)
        nav: list[InlineKeyboardButton] = []

        if page > 0:
            nav.append(
                InlineKeyboardButton(
                    text="⬅️",
                    callback_data=f"stats_page:{stage}:{page - 1}",
                )
            )

        nav.append(
            InlineKeyboardButton(
                text=f"{STAGE_LABELS[stage]} {page + 1}/{max_page + 1}",
                callback_data="stats_noop",
            )
        )

        if page < max_page:
            nav.append(
                InlineKeyboardButton(
                    text="➡️",
                    callback_data=f"stats_page:{stage}:{page + 1}",
                )
            )

        rows.append(nav)

    rows.append([InlineKeyboardButton(text="🔄 Обновить", callback_data="stats_overview")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def build_stats_overview(admin_id: int) -> tuple[str, str, InlineKeyboardMarkup]:
    counts = await fetch_stage_counts()
    pages = get_admin_stats_pages(admin_id)

    rich_parts = [
        "<h2>📊 Статистика онбординга</h2>",
        f"""
<table bordered striped>
  <tr><th>Этап</th><th>Кол-во</th></tr>
  <tr><td>👥 Всего в боте</td><td>{counts["all"]}</td></tr>
  <tr><td>🆕 Без правил</td><td>{counts["start"]}</td></tr>
  <tr><td>📜 Правила ✓, анкета нет</td><td>{counts["rules"]}</td></tr>
  <tr><td>📝 Анкета ✓, согласие нет</td><td>{counts["form"]}</td></tr>
  <tr><td>🔐 Согласие ✓, не в чате</td><td>{counts["pd"]}</td></tr>
  <tr><td>✅ Вступили в чат</td><td>{counts["joined"]}</td></tr>
</table>
""",
        "<p>Списки пользователей по этапам:</p>",
    ]

    fallback_parts = [
        "<b>📊 Статистика онбординга</b>",
        (
            f"👥 Всего в боте: <b>{counts['all']}</b>\n"
            f"🆕 Без правил: <b>{counts['start']}</b>\n"
        f"📜 Правила ✓, анкета нет: <b>{counts['rules']}</b>\n"
        f"📝 Анкета ✓, согласие нет: <b>{counts['form']}</b>\n"
        f"🔐 Согласие ✓, не в чате: <b>{counts['pd']}</b>\n"
            f"✅ Вступили в чат: <b>{counts['joined']}</b>"
        ),
        "<b>Списки пользователей по этапам:</b>",
    ]

    for stage in STAGE_ORDER:
        users, total = await fetch_users(
            stage,
            pages[stage],
            per_page=STATS_TABLE_PER_PAGE,
        )
        rich_parts.append(build_stage_details_rich(stage, users, total, pages[stage]))
        fallback_parts.append(
            build_stage_details_fallback(stage, users, total, pages[stage])
        )

    rich_html = "\n".join(rich_parts)
    fallback_html = "\n\n".join(fallback_parts)
    keyboard = stats_pagination_keyboard(pages, counts)
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

    reset_admin_stats_pages(message.from_user.id)
    rich_html, fallback_html, keyboard = await build_stats_overview(message.from_user.id)
    await send_rich_or_html(
        bot=bot,
        bot_token=BOT_TOKEN,
        chat_id=message.from_user.id,
        rich_html=rich_html,
        fallback_html=fallback_html,
        reply_markup=keyboard,
    )


@router.callback_query(F.data == "stats_overview")
async def stats_overview_callback(callback: CallbackQuery, bot: Bot) -> None:
    if not is_admin(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return

    reset_admin_stats_pages(callback.from_user.id)
    rich_html, fallback_html, keyboard = await build_stats_overview(callback.from_user.id)
    await edit_rich_or_html(
        bot=bot,
        bot_token=BOT_TOKEN,
        message=callback.message,
        rich_html=rich_html,
        fallback_html=fallback_html,
        reply_markup=keyboard,
    )
    await callback.answer()


@router.callback_query(F.data == "stats_noop")
async def stats_noop_callback(callback: CallbackQuery) -> None:
    await callback.answer()


@router.callback_query(F.data.startswith("stats_page:"))
async def stats_page_callback(callback: CallbackQuery, bot: Bot) -> None:
    if not is_admin(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return

    _, stage, page_raw = callback.data.split(":", 2)
    page = int(page_raw)

    if stage not in STAGE_ORDER:
        await callback.answer("Неизвестный этап", show_alert=True)
        return

    pages = get_admin_stats_pages(callback.from_user.id)
    _, total = await fetch_users(stage, page, per_page=STATS_TABLE_PER_PAGE)
    max_page = max((total - 1) // STATS_TABLE_PER_PAGE, 0)

    if page < 0 or page > max_page:
        await callback.answer("Страница не найдена", show_alert=True)
        return

    pages[stage] = page
    rich_html, fallback_html, keyboard = await build_stats_overview(callback.from_user.id)
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


def format_user_button_label(row: dict[str, Any]) -> str:
    identity = format_user_identity(row)
    stage = user_stage_label(row)
    label = f"{identity} · {stage}"
    if len(label) <= 64:
        return label
    return f"{identity[:58]}…" if len(identity) > 58 else identity


def build_send_picker_text(page: int, total: int) -> str:
    max_page = max((total - 1) // SEND_USERS_PER_PAGE, 0)
    return (
        f"<b>Выберите получателя</b>\n"
        f"Страница {page + 1} из {max_page + 1} · всего {total}"
    )


def send_user_picker_keyboard(
    users: list[dict[str, Any]],
    page: int,
    total: int,
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(
                text=format_user_button_label(user),
                callback_data=f"send_pick:{user['telegram_id']}",
            )
        ]
        for user in users
    ]

    max_page = max((total - 1) // SEND_USERS_PER_PAGE, 0)
    nav: list[InlineKeyboardButton] = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"send_users:{page - 1}"))
    if page < max_page:
        nav.append(InlineKeyboardButton(text="➡️", callback_data=f"send_users:{page + 1}"))
    if nav:
        rows.append(nav)

    rows.append([InlineKeyboardButton(text="❌ Отмена", callback_data="send_cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


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
        users, total = await fetch_users("all", 0, per_page=SEND_USERS_PER_PAGE)
        if total == 0:
            await callback.message.answer("В базе пока нет пользователей.")
            await clear_send_state(state)
        else:
            await callback.message.answer(
                build_send_picker_text(0, total),
                parse_mode=ParseMode.HTML,
                reply_markup=send_user_picker_keyboard(users, 0, total),
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


@router.callback_query(F.data.startswith("send_users:"))
async def send_users_page_callback(callback: CallbackQuery) -> None:
    if not is_admin(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return

    page = int(callback.data.split(":", 1)[1])
    users, total = await fetch_users("all", page, per_page=SEND_USERS_PER_PAGE)
    max_page = max((total - 1) // SEND_USERS_PER_PAGE, 0)

    if page < 0 or page > max_page:
        await callback.answer("Страница не найдена", show_alert=True)
        return

    await callback.message.edit_text(
        build_send_picker_text(page, total),
        parse_mode=ParseMode.HTML,
        reply_markup=send_user_picker_keyboard(users, page, total),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("send_pick:"))
async def send_pick_user_callback(callback: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return

    user_id = int(callback.data.split(":", 1)[1])
    user = await fetch_user_by_id(user_id)
    if not user:
        await callback.answer("Пользователь не найден", show_alert=True)
        return

    identity = format_user_identity(user)
    await state.update_data(
        target_type="one",
        target_user_id=user["telegram_id"],
        target_label=identity,
        recipient_count=1,
    )
    await state.set_state(SendMessageStates.waiting_message)
    await callback.message.answer(
        f"Получатель: <b>{identity}</b> (<code>{user['telegram_id']}</code>)\n"
        f"Этап: {user_stage_label(user)}\n\n"
        "Отправьте текст сообщения. Поддерживается HTML-разметка.",
        parse_mode=ParseMode.HTML,
    )
    await callback.answer()


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
