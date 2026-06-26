import time

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery

from app.config import BOT_TOKEN, PD_VERSION, TARGET_CHAT_ID
from app.db.repository import save_invite_link, set_accepted, upsert_user
from app.keyboards.onboarding import join_keyboard

router = Router()


@router.callback_query(F.data == "decline_pd")
async def decline_pd(callback: CallbackQuery) -> None:
    await callback.message.answer(
        "Без согласия на обработку персональных данных доступ к чату не предоставляется."
    )
    await callback.answer()


@router.callback_query(F.data == "accept_pd")
async def accept_pd(callback: CallbackQuery, bot: Bot) -> None:
    await upsert_user(callback)
    await set_accepted(
        callback.from_user.id,
        "accepted_pd",
        "pd_version",
        "pd_accepted_at",
        PD_VERSION,
    )

    invite = await bot.create_chat_invite_link(
        chat_id=TARGET_CHAT_ID,
        name=f"onboarding_{callback.from_user.id}",
        expire_date=int(time.time()) + 60 * 10,
        creates_join_request=True,
    )

    await save_invite_link(callback.from_user.id, invite.invite_link)

    await callback.message.answer(
        "✅ Спасибо! Все этапы пройдены.\n\n"
        "Теперь нажмите кнопку ниже и подайте заявку на вступление. "
        "Если всё пройдено корректно, бот одобрит заявку автоматически.",
        reply_markup=join_keyboard(invite.invite_link),
    )
    await callback.answer("Согласие принято")
