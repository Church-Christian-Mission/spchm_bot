from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery

_EXPIRED_QUERY_MARKERS = (
    "query is too old",
    "query id is invalid",
    "response timeout expired",
)


async def safe_answer_callback(
    callback: CallbackQuery,
    text: str | None = None,
    *,
    show_alert: bool = False,
) -> bool:
    """Answer callback query; ignore expired/invalid query errors."""
    try:
        await callback.answer(text=text, show_alert=show_alert)
        return True
    except TelegramBadRequest as exc:
        message = (exc.message or "").lower()
        if any(marker in message for marker in _EXPIRED_QUERY_MARKERS):
            return False
        raise
