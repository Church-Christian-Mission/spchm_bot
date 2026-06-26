from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from app.config import BOT_TOKEN, RULES_VERSION
from app.db.repository import set_accepted, upsert_user
from app.handlers.questionnaire.service import start_questionnaire
from app.keyboards.onboarding import rules_keyboard
from app.services.rich_messages import send_rich_or_html
from app.texts import RULES_FALLBACK_HTML, RULES_RICH_HTML

router = Router()


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
async def accept_rules(callback: CallbackQuery, state: FSMContext) -> None:
    await upsert_user(callback)
    await set_accepted(
        callback.from_user.id,
        "accepted_rules",
        "rules_version",
        "rules_accepted_at",
        RULES_VERSION,
    )

    await start_questionnaire(callback.message, callback.from_user, state)
    await callback.answer("Правила подтверждены")
