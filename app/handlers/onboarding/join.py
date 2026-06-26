from aiogram import Bot, Router
from aiogram.types import ChatJoinRequest

from app.db.repository import mark_joined
from app.services.onboarding import has_completed_onboarding

router = Router()


@router.chat_join_request()
async def on_chat_join_request(join_request: ChatJoinRequest, bot: Bot) -> None:
    user_id = join_request.from_user.id

    if await has_completed_onboarding(user_id):
        await join_request.approve()
        await mark_joined(user_id)

        try:
            await bot.send_message(
                chat_id=user_id,
                text="🎉 Ваша заявка одобрена. Добро пожаловать в чат!",
            )
        except Exception:
            pass
    else:
        await join_request.decline()

        try:
            await bot.send_message(
                chat_id=user_id,
                text=(
                    "Заявка отклонена, потому что вы ещё не прошли все этапы ознакомления.\n\n"
                    "Нажмите /start и пройдите правила, анкету и согласие."
                ),
            )
        except Exception:
            pass
