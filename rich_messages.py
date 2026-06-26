import os
from typing import Optional, Sequence

import aiohttp
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup


USE_RICH_MESSAGES = os.getenv("USE_RICH_MESSAGES", "1") == "1"


async def send_rich_or_html(
    *,
    bot: Bot,
    bot_token: str,
    chat_id: int,
    rich_html: str,
    fallback_html: str,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
) -> None:
    """
    Отправляет Telegram Rich Message через Bot API 10.1.

    Если Rich Messages недоступны или Telegram вернул ошибку,
    автоматически отправляет обычное HTML-сообщение через aiogram.

    Почему так:
    - Rich Messages появились недавно.
    - Обёртки aiogram могут не сразу поддерживать sendRichMessage.
    - Обычный HTML нужен как стабильный fallback.
    """

    if not USE_RICH_MESSAGES:
        await bot.send_message(chat_id=chat_id, text=fallback_html, reply_markup=reply_markup)
        return

    payload = {
        "chat_id": chat_id,
        "rich_message": {
            "html": rich_html,
            "skip_entity_detection": True,
        },
    }

    if reply_markup is not None:
        payload["reply_markup"] = reply_markup.model_dump(exclude_none=True)

    url = f"https://api.telegram.org/bot{bot_token}/sendRichMessage"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=15) as response:
                data = await response.json(content_type=None)

        if not data.get("ok"):
            await bot.send_message(chat_id=chat_id, text=fallback_html, reply_markup=reply_markup)

    except Exception:
        await bot.send_message(chat_id=chat_id, text=fallback_html, reply_markup=reply_markup)


async def send_rich_or_html_parts(
    *,
    bot: Bot,
    bot_token: str,
    chat_id: int,
    parts: Sequence[tuple[str, str]],
    reply_markup: Optional[InlineKeyboardMarkup] = None,
) -> None:
    if not parts:
        return

    for rich_html, fallback_html in parts[:-1]:
        await send_rich_or_html(
            bot=bot,
            bot_token=bot_token,
            chat_id=chat_id,
            rich_html=rich_html,
            fallback_html=fallback_html,
        )

    rich_html, fallback_html = parts[-1]
    await send_rich_or_html(
        bot=bot,
        bot_token=bot_token,
        chat_id=chat_id,
        rich_html=rich_html,
        fallback_html=fallback_html,
        reply_markup=reply_markup,
    )
