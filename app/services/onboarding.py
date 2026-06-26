from app.db.repository import get_status

__all__ = ["has_completed_onboarding"]


async def has_completed_onboarding(user_id: int) -> bool:
    status = await get_status(user_id)
    return bool(
        status
        and status.accepted_rules
        and status.questionnaire_completed
        and status.accepted_pd
    )
