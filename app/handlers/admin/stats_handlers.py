from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from app.config import ADMIN_IDS, BOT_TOKEN, FORMS_TABLE_PER_PAGE, STATS_TABLE_PER_PAGE
from app.db.repository import fetch_form_users, fetch_users
from app.handlers.admin.auth import is_admin, send_access_denied
from app.handlers.admin.constants import FORM_FILTERS, STAGE_ORDER, STAGES
from app.handlers.admin.state import (
    get_admin_form_state,
    get_admin_stats_pages,
    reset_admin_form_state,
    reset_admin_stats_pages,
)
from app.handlers.admin.views import build_forms_view, build_stats_overview
from app.services.rich_messages import edit_rich_or_html, send_rich_or_html

router = Router()


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
    _, total = await fetch_users(stage, STAGES, page, per_page=STATS_TABLE_PER_PAGE)
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


@router.callback_query(F.data == "stats_forms")
async def stats_forms_callback(callback: CallbackQuery, bot: Bot) -> None:
    if not is_admin(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return

    reset_admin_form_state(callback.from_user.id)
    rich_html, fallback_html, keyboard = await build_forms_view(callback.from_user.id)
    await edit_rich_or_html(
        bot=bot,
        bot_token=BOT_TOKEN,
        message=callback.message,
        rich_html=rich_html,
        fallback_html=fallback_html,
        reply_markup=keyboard,
    )
    await callback.answer()


@router.callback_query(F.data == "stats_forms_refresh")
async def stats_forms_refresh_callback(callback: CallbackQuery, bot: Bot) -> None:
    if not is_admin(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return

    rich_html, fallback_html, keyboard = await build_forms_view(callback.from_user.id)
    await edit_rich_or_html(
        bot=bot,
        bot_token=BOT_TOKEN,
        message=callback.message,
        rich_html=rich_html,
        fallback_html=fallback_html,
        reply_markup=keyboard,
    )
    await callback.answer("Обновлено")


@router.callback_query(F.data.startswith("form_filter:"))
async def form_filter_callback(callback: CallbackQuery, bot: Bot) -> None:
    if not is_admin(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return

    filter_key = callback.data.split(":", 1)[1]
    if filter_key not in FORM_FILTERS:
        await callback.answer("Неизвестный фильтр", show_alert=True)
        return

    state = get_admin_form_state(callback.from_user.id)
    state["filter"] = filter_key
    state["page"] = 0

    rich_html, fallback_html, keyboard = await build_forms_view(callback.from_user.id)
    await edit_rich_or_html(
        bot=bot,
        bot_token=BOT_TOKEN,
        message=callback.message,
        rich_html=rich_html,
        fallback_html=fallback_html,
        reply_markup=keyboard,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("form_page:"))
async def form_page_callback(callback: CallbackQuery, bot: Bot) -> None:
    if not is_admin(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return

    page = int(callback.data.split(":", 1)[1])
    state = get_admin_form_state(callback.from_user.id)

    _, total = await fetch_form_users(state["filter"], FORM_FILTERS, page, FORMS_TABLE_PER_PAGE)
    max_page = max((total - 1) // FORMS_TABLE_PER_PAGE, 0)

    if page < 0 or page > max_page:
        await callback.answer("Страница не найдена", show_alert=True)
        return

    state["page"] = page
    rich_html, fallback_html, keyboard = await build_forms_view(callback.from_user.id)
    await edit_rich_or_html(
        bot=bot,
        bot_token=BOT_TOKEN,
        message=callback.message,
        rich_html=rich_html,
        fallback_html=fallback_html,
        reply_markup=keyboard,
    )
    await callback.answer()
