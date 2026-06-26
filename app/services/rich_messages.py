from typing import Optional

import aiohttp
from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import InlineKeyboardMarkup, Message

from app.config import USE_RICH_MESSAGES


def _rich_message_payload(rich_html: str) -> dict:
    return {
        "html": rich_html,
        "skip_entity_detection": True,
    }


def _reply_markup_payload(reply_markup: Optional[InlineKeyboardMarkup]) -> dict:
    if reply_markup is None:
        return {}
    return {"reply_markup": reply_markup.model_dump(exclude_none=True)}


async def send_rich_or_html(
    *,
    bot: Bot,
    bot_token: str,
    chat_id: int,
    rich_html: str,
    fallback_html: str,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
) -> None:
    if not USE_RICH_MESSAGES:
        await bot.send_message(chat_id=chat_id, text=fallback_html, reply_markup=reply_markup)
        return

    payload = {
        "chat_id": chat_id,
        "rich_message": _rich_message_payload(rich_html),
        **_reply_markup_payload(reply_markup),
    }

    url = f"https://api.telegram.org/bot{bot_token}/sendRichMessage"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=15) as response:
                data = await response.json(content_type=None)

        if not data.get("ok"):
            await bot.send_message(chat_id=chat_id, text=fallback_html, reply_markup=reply_markup)

    except Exception:
        await bot.send_message(chat_id=chat_id, text=fallback_html, reply_markup=reply_markup)


async def _edit_message_rich(
    *,
    bot_token: str,
    message: Message,
    rich_html: str,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
) -> bool:
    payload = {
        "chat_id": message.chat.id,
        "message_id": message.message_id,
        "rich_message": _rich_message_payload(rich_html),
        **_reply_markup_payload(reply_markup),
    }
    url = f"https://api.telegram.org/bot{bot_token}/editMessageText"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=15) as response:
                data = await response.json(content_type=None)
        return bool(data.get("ok"))
    except Exception:
        return False


async def edit_rich_or_html(
    *,
    bot: Bot,
    bot_token: str,
    message: Message,
    rich_html: str,
    fallback_html: str,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
) -> None:
    if USE_RICH_MESSAGES and await _edit_message_rich(
        bot_token=bot_token,
        message=message,
        rich_html=rich_html,
        reply_markup=reply_markup,
    ):
        return

    try:
        await message.edit_text(
            text=fallback_html,
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML,
        )
    except TelegramBadRequest:
        try:
            await message.delete()
        except TelegramBadRequest:
            pass

        await send_rich_or_html(
            bot=bot,
            bot_token=bot_token,
            chat_id=message.chat.id,
            rich_html=rich_html,
            fallback_html=fallback_html,
            reply_markup=reply_markup,
        )
