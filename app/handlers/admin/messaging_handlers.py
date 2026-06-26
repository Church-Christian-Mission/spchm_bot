import asyncio
from typing import Any

from aiogram import Bot, F, Router
from aiogram.enums import ParseMode
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from app.config import ADMIN_IDS, BROADCAST_DELAY_SEC, BOT_TOKEN, SEND_USERS_PER_PAGE
from app.db.repository import fetch_all_user_ids, fetch_user_by_id, fetch_users
from app.handlers.admin.auth import is_admin, send_access_denied
from app.handlers.admin.constants import STAGES
from app.services.callbacks import safe_answer_callback
from app.services.user_display import format_user_identity, user_stage_label

router = Router()


class SendMessageStates(StatesGroup):
    waiting_message = State()
    waiting_confirm = State()


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
        await safe_answer_callback(callback, "Недостаточно прав", show_alert=True)
        return

    await safe_answer_callback(callback)
    await clear_send_state(state)
    await callback.message.answer("Отправка отменена.")


@router.callback_query(F.data.startswith("send_target:"))
async def send_target_callback(callback: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(callback.from_user.id):
        await safe_answer_callback(callback, "Недостаточно прав", show_alert=True)
        return

    target_type = callback.data.split(":", 1)[1]
    if target_type == "one":
        await safe_answer_callback(callback)
        users, total = await fetch_users("all", STAGES, 0, per_page=SEND_USERS_PER_PAGE)
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
        await safe_answer_callback(callback)
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
        await safe_answer_callback(callback, "Неизвестный тип рассылки", show_alert=True)


@router.callback_query(F.data.startswith("send_users:"))
async def send_users_page_callback(callback: CallbackQuery) -> None:
    if not is_admin(callback.from_user.id):
        await safe_answer_callback(callback, "Недостаточно прав", show_alert=True)
        return

    page = int(callback.data.split(":", 1)[1])
    users, total = await fetch_users("all", STAGES, page, per_page=SEND_USERS_PER_PAGE)
    max_page = max((total - 1) // SEND_USERS_PER_PAGE, 0)

    if page < 0 or page > max_page:
        await safe_answer_callback(callback, "Страница не найдена", show_alert=True)
        return

    await safe_answer_callback(callback)
    await callback.message.edit_text(
        build_send_picker_text(page, total),
        parse_mode=ParseMode.HTML,
        reply_markup=send_user_picker_keyboard(users, page, total),
    )


@router.callback_query(F.data.startswith("send_pick:"))
async def send_pick_user_callback(callback: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(callback.from_user.id):
        await safe_answer_callback(callback, "Недостаточно прав", show_alert=True)
        return

    user_id = int(callback.data.split(":", 1)[1])
    user = await fetch_user_by_id(user_id)
    if not user:
        await safe_answer_callback(callback, "Пользователь не найден", show_alert=True)
        return

    await safe_answer_callback(callback)
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
        await safe_answer_callback(callback, "Недостаточно прав", show_alert=True)
        return

    data = await state.get_data()
    text = data.get("message_text", "").strip()
    if not text:
        await safe_answer_callback(callback, "Текст сообщения пустой", show_alert=True)
        await clear_send_state(state)
        return

    await safe_answer_callback(callback, "Отправляю…")
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
        return

    await clear_send_state(state)
    await callback.message.answer(
        f"Готово.\nОтправлено: <b>{sent}</b>\nНе доставлено: <b>{failed}</b>",
        parse_mode=ParseMode.HTML,
    )
