from typing import Any

from app.db.repository import get_status


async def has_completed_onboarding(user_id: int) -> bool:
    status = await get_status(user_id)
    return bool(
        status
        and status.accepted_rules
        and status.questionnaire_completed
        and status.accepted_pd
    )


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


def format_form_full_name(row: dict[str, Any]) -> str:
    form_name = " ".join(
        part
        for part in (
            row.get("surname") or "",
            row.get("given_name") or "",
            row.get("patronymic") or "",
        )
        if part
    ).strip()
    if form_name:
        return form_name
    return format_user_identity(row)


def html_cell(value: str | None) -> str:
    if not value:
        return "—"
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
