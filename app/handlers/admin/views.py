from typing import Any

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.config import FORMS_TABLE_PER_PAGE, STATS_TABLE_PER_PAGE
from app.db.repository import fetch_form_users, fetch_stage_counts, fetch_users
from app.handlers.admin.constants import (
    FORM_FILTER_ORDER,
    FORM_FILTERS,
    STAGE_LABELS,
    STAGE_ORDER,
    STAGES,
)
from app.handlers.admin.state import get_admin_form_state, get_admin_stats_pages
from app.services.user_display import (
    format_form_full_name,
    format_user_identity,
    html_cell,
    user_stage_label,
)


def build_forms_table_rich(users: list[dict[str, Any]]) -> str:
    if not users:
        return "<p>По выбранному фильтру никого нет.</p>"

    rows = "".join(
        (
            "<tr>"
            f"<td>{html_cell(format_form_full_name(user))}</td>"
            f"<td>{html_cell(user.get('phone'))}</td>"
            f"<td>{html_cell(user.get('city'))}</td>"
            f"<td>{html_cell(user.get('church_name'))}</td>"
            f"<td>{user_stage_label(user)}</td>"
            f"<td><code>{user['telegram_id']}</code></td>"
            "</tr>"
        )
        for user in users
    )
    return (
        "<table bordered striped>"
        "<tr><th>ФИО</th><th>Телефон</th><th>Город</th><th>Церковь</th><th>Этап</th><th>ID</th></tr>"
        f"{rows}"
        "</table>"
    )


def build_forms_table_fallback(users: list[dict[str, Any]]) -> str:
    if not users:
        return "По выбранному фильтру никого нет."

    lines = []
    for user in users:
        lines.append(
            f"• <b>{format_form_full_name(user)}</b>\n"
            f"  📱 {user.get('phone') or '—'} · 🏙 {user.get('city') or '—'}\n"
            f"  ⛪ {user.get('church_name') or '—'} · {user_stage_label(user)}\n"
            f"  ID: <code>{user['telegram_id']}</code>"
        )
    return "\n\n".join(lines)


def forms_filter_keyboard(active_filter: str) -> list[list[InlineKeyboardButton]]:
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []

    for key in FORM_FILTER_ORDER:
        label = FORM_FILTERS[key]["label"]
        text = f"• {label}" if key == active_filter else label
        row.append(InlineKeyboardButton(text=text, callback_data=f"form_filter:{key}"))
        if len(row) == 2:
            rows.append(row)
            row = []

    if row:
        rows.append(row)

    return rows


def forms_pagination_keyboard(filter_key: str, page: int, total: int) -> InlineKeyboardMarkup:
    max_page = max((total - 1) // FORMS_TABLE_PER_PAGE, 0)
    rows = forms_filter_keyboard(filter_key)

    nav: list[InlineKeyboardButton] = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"form_page:{page - 1}"))
    nav.append(
        InlineKeyboardButton(
            text=f"Стр. {page + 1}/{max_page + 1}",
            callback_data="stats_noop",
        )
    )
    if page < max_page:
        nav.append(InlineKeyboardButton(text="➡️", callback_data=f"form_page:{page + 1}"))
    rows.append(nav)

    rows.append([InlineKeyboardButton(text="📊 Сводка", callback_data="stats_overview")])
    rows.append([InlineKeyboardButton(text="🔄 Обновить", callback_data="stats_forms_refresh")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def build_forms_view(admin_id: int) -> tuple[str, str, InlineKeyboardMarkup]:
    state = get_admin_form_state(admin_id)
    filter_key = state["filter"]
    page = state["page"]
    users, total = await fetch_form_users(filter_key, FORM_FILTERS, page, FORMS_TABLE_PER_PAGE)
    max_page = max((total - 1) // FORMS_TABLE_PER_PAGE, 0)
    filter_label = FORM_FILTERS[filter_key]["label"]

    rich_html = (
        "<h2>📋 Таблица анкет</h2>\n"
        f"<p>Фильтр: <b>{filter_label}</b> · "
        f"страница {page + 1} из {max_page + 1} · всего {total}</p>\n"
        f"{build_forms_table_rich(users)}"
    )
    fallback_html = (
        f"<b>📋 Таблица анкет</b>\n"
        f"Фильтр: <b>{filter_label}</b>\n"
        f"Страница {page + 1} из {max_page + 1} · всего {total}\n\n"
        f"{build_forms_table_fallback(users)}"
    )
    keyboard = forms_pagination_keyboard(filter_key, page, total)
    return rich_html, fallback_html, keyboard


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

    rows.append([InlineKeyboardButton(text="📋 Таблица анкет", callback_data="stats_forms")])
    rows.append([InlineKeyboardButton(text="🔄 Обновить", callback_data="stats_overview")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def build_stats_overview(admin_id: int) -> tuple[str, str, InlineKeyboardMarkup]:
    counts = await fetch_stage_counts(STAGES)
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
            STAGES,
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
